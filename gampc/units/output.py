# coding: utf-8
#
# Graphical Asynchronous Music Player Client
#
# Copyright (C) 2015-2022 Itaï BEN YAACOV
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
from gi.repository import Gio
from gi.repository import Gdk

import ampd

from ..util import ssde
from ..util import resource
from ..util import unit


class __unit__(unit.UnitMixinServer, unit.Unit):
    def __init__(self, name, manager):
        super().__init__(name, manager)

        self.outputs = []

        self.output_menu = Gio.Menu()

        self.app_menu_provider = self.new_resource_provider('app.menu')
        self.app_menu_provider.add_resources(
            resource.MenuPath('server/server/output/output_menu', _("Outputs (<Ctrl> to toggle)"), instance=self.output_menu),
        )

        self.app_action_provider = self.new_resource_provider('app.action')

    def shutdown(self):
        self.clean_outputs()
        super().shutdown()

    def client_connected_cb(self, client):
        self.idle_output()

    @ampd.task
    async def idle_output(self):
        try:
            while True:
                self.clean_outputs()
                self.refresh_outputs(await self.ampd.outputs())
                await self.ampd.idle(ampd.OUTPUT)
        except ampd.ConnectionError:
            self.clean_outputs()
            self.outputs = []

    def clean_outputs(self):
        self.app_action_provider.remove_all_resources()
        self.output_menu.remove_all()

    def refresh_outputs(self, outputs):
        self.outputs = []
        for output in outputs:
            if output['plugin'] == 'dummy':
                continue
            output['action'] = 'output-' + output['outputid']
            self.app_action_provider.add_resource(resource.ActionModel(output['action'], self.action_output_activate_cb, state=GLib.Variant.new_boolean(int(output['outputenabled'])), dangerous=True))
            resource.MenuAction('app.' + output['action'], output['outputname']).insert_into(self.output_menu)
            self.outputs.append(output)

    @ampd.task
    async def action_output_activate_cb(self, action, parameter):
        output_id = action.get_name().split('-', 1)[1]
        if Gdk.Keymap.get_default().get_modifier_state() & Gdk.ModifierType.CONTROL_MASK:
            await self.ampd.toggleoutput(output_id)
        elif all(map(lambda output: output['outputid'] == output_id or output['outputenabled'] == '0', await self.ampd.outputs())) and self.unit_server.ampd_server_properties.state == 'play':
            await self.ampd.command_list([self.ampd.pause(1), self.ampd.disableoutput(output_id), self.ampd.enableoutput(output_id), self.ampd.pause(0)])
        else:
            await self.ampd.enableoutput(output_id)
            await self.ampd.command_list(self.ampd.disableoutput(output['outputid']) for output in self.outputs if output['outputid'] != output_id)
