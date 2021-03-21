# coding: utf-8
#
# Graphical Asynchronous Music Player Client
#
# Copyright (C) 2015 Itaï BEN YAACOV
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import Gtk

import asyncio

import ampd

from gampc.util import ssde
from gampc.util import resource
from gampc.util import unit


class __unit__(unit.UnitWithServer):
    REQUIRED_UNITS = ['server']

    def __init__(self, name, manager):
        super().__init__(name, manager)

        self.unit_server.connect('notify::server-partition', self.notify_server_partition_cb)
        self.unit_server.ampd_client.connect('client-connected', self.client_connected_cb)

        self.outputs = []
        self.partitions = None

        self.output_menu = Gio.Menu()
        self.partition_section = Gio.Menu()

        self.new_resource_provider('app.action').add_resources(
            resource.ActionModel('partition-go', self.action_partition_go_del_cb, parameter_type=GLib.VariantType.new('s')),
            resource.ActionModel('partition-del', self.action_partition_go_del_cb, parameter_type=GLib.VariantType.new('s')),
            resource.ActionModel('partition-move-output', self.action_partition_move_output_cb, parameter_type=GLib.VariantType.new('(ss)')),
            resource.ActionModel('partition-new', self.action_partition_new_cb),
        )

        self.app_menu_provider = self.new_resource_provider('app.menu')
        self.app_menu_provider.add_resources(
            resource.MenuPath('server/server/partition/output', _("Outputs (<Ctrl> to toggle)"), instance=self.output_menu),
            resource.MenuPath('server/server/partition/parition', instance=self.partition_section),
        )

        self.app_output_action_provider = self.new_resource_provider('app.action')
        self.app_user_action_provider = self.new_resource_provider('app.user-action')

    def shutdown(self):
        self.unit_server.ampd_client.disconnect_by_func(self.client_connected_cb)
        self.unit_server.disconnect_by_func(self.notify_server_partition_cb)
        super().shutdown()

    def client_connected_cb(self, client):
        self.idle_output()
        self.idle_partition()

    @ampd.task
    async def idle_output(self):
        try:
            while True:
                self.clean_outputs()
                self.refresh_outputs(await self.ampd.outputs())
                # self.outputs = await self.ampd.outputs()
                # self.refresh_outputs()
                # self.refresh_partitions()
                await self.ampd.idle(ampd.OUTPUT)
        except asyncio.CancelledError:
            self.clean_outputs()
            self.outputs = []
            raise

    @ampd.task
    async def idle_partition(self):
        if 'partition' not in await self.ampd.status():
            self.partitions = None
            self.refresh_partitions()
            return
        while True:
            self.partitions = await self.ampd.listpartitions()
            self.refresh_partitions()
            await self.ampd.idle(ampd.PARTITION)

    def notify_server_partition_cb(self, unit_server, param):
        self.refresh_partitions()

    def clean_outputs(self):
        self.app_output_action_provider.remove_all_resources()
        self.output_menu.remove_all()

    def refresh_outputs(self, outputs):
        self.outputs = []
        for output in outputs:
            if output['plugin'] == 'dummy':
                continue
            output['action'] = 'output-' + output['outputid']
            self.app_output_action_provider.add_resource(resource.ActionModel(output['action'], self.action_output_activate_cb, state=GLib.Variant.new_boolean(int(output['outputenabled'])), dangerous=True))
            resource.MenuAction('app.' + output['action'], output['outputname']).insert_into(self.output_menu)
            self.outputs.append(output)

    def refresh_partitions(self):
        self.partition_section.remove_all()
        if self.partitions is not None:
            resource.MenuPath('menu', _("P_artitions (current: {partition})").format(partition=self.unit_server.server_partition), is_submenu=True).insert_into(self.partition_section)
            for partition in self.partitions:
                if partition == self.unit_server.server_partition:
                    continue
                resource.MenuPath('menu/' + partition, _("Partition {partition}").format(partition=partition), is_submenu=True).insert_into(self.partition_section)
                resource.MenuAction('menu/' + partition + '/app.partition-go("{partition}")'.format(partition=partition), _("Choose")).insert_into(self.partition_section)
                resource.MenuAction('menu/' + partition + '/app.partition-del("{partition}")'.format(partition=partition), _("Delete")).insert_into(self.partition_section)
                for output in self.outputs:
                    resource.MenuAction('menu/' + partition + '/app.partition-move-output(("{partition}","{output}"))'.format(partition=partition, output=output['outputname']), _("Move output '{outputname}' here").format_map(output)).insert_into(self.partition_section)
            resource.MenuAction('menu/app.partition-new', _("New partition")).insert_into(self.partition_section)

    @ampd.task
    async def action_output_activate_cb(self, action, parameter):
        output_id = action.get_name().split('-', 1)[1]
        if Gdk.Keymap.get_default().get_modifier_state() & Gdk.ModifierType.CONTROL_MASK:
            await self.ampd.toggleoutput(output_id)
        elif all(map(lambda output: output['outputid'] == output_id or output['outputenabled'] == '0', await self.ampd.outputs())) and self.unit_server.ampd_server_properties.state == 'play':
            await self.ampd.command_list([self.ampd.pause(1), self.ampd.disableoutput(output_id), self.ampd.enableoutput(output_id), self.ampd.pause(0)])
        else:
            await self.ampd.enableoutput(output_id)
            await self.ampd.command_list(self.ampd.disableoutput(output['outputid']) for output in self.outputs if output['outputid'] is not output_id)

    @ampd.task
    async def action_partition_go_del_cb(self, action, parameter):
        partition = parameter.unpack()
        action_name = action.get_name().split('-', 1)[1]
        if action_name == 'go':
            self.unit_server.server_profile_desired = self.unit_server.server_profile + ',' + partition
        elif action_name == 'del':
            await self.ampd.delpartition(partition)

    @ampd.task
    async def action_partition_move_output_cb(self, action, parameter):
        partition, output = parameter.unpack()
        await self.ampd.command_list(
            self.ampd.partition(partition),
            self.ampd.moveoutput(output),
            self.ampd.partition(self.unit_server.server_partition),
        )

    @ampd.task
    async def action_partition_new_cb(self, action, parameter):
        label = _("New partition name")
        new_name = "<{}>".format(label)
        struct = ssde.Text(label=label,
                           default=new_name,
                           validator=lambda x: x != new_name)
        # value = await struct.edit_async(self.get_active_window())
        value = await struct.edit_async()
        if value:
            await self.ampd.newpartition(value)
