# coding: utf-8
#
# Graphical Asynchronous Music Player Client
#
# Copyright (C) Itaï BEN YAACOV
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

from ..util import action
from ..util import misc
from ..util import unit

from . import mixins


class __unit__(mixins.UnitServerMixin, unit.Unit):
    def __init__(self, manager):
        super().__init__(manager)

        self.require('persistent')

        self.outputs = []

        self.actions = Gio.SimpleActionGroup()
        self.menu = Gio.Menu()

    def cleanup(self):
        self.clean_outputs()
        super().cleanup()

    def client_connected_cb(self, client):
        self.idle_output()

    @ampd.task
    async def idle_output(self):
        try:
            while True:
                self.clean_outputs()
                outputs = await self.ampd.outputs()
                family = action.ActionInfoFamily(self.generate_output_actions(outputs), 'app')
                self.menu.append_section(None, family.get_menu())
                family.add_to_action_map(self.actions, protect=self.unit_persistent.protect)
                await self.ampd.idle(ampd.OUTPUT)
        except ampd.ConnectionError:
            self.clean_outputs()
            self.outputs = []

    def clean_outputs(self):
        self.menu.remove_all()
        for output in self.outputs:
            self.actions.remove_action(output['action'])

    def generate_output_actions(self, outputs):
        for output in outputs:
            if output['plugin'] == 'dummy':
                continue
            self.outputs.append(output)
            output['action'] = 'output-' + output['outputid']
            yield action.ActionInfo(output['action'], self.action_output_activate_cb, output['outputname'], state=GLib.Variant.new_boolean(int(output['outputenabled'])), dangerous=True)

    @ampd.task
    async def action_output_activate_cb(self, action, parameter):
        output_id = action.get_name().split('-', 1)[1]
        if misc.get_modifier_state() & Gdk.ModifierType.CONTROL_MASK:
            await self.ampd.toggleoutput(output_id)
        elif all(map(lambda output: output['outputid'] == output_id or output['outputenabled'] == '0', await self.ampd.outputs())) and self.unit_server.ampd_server_properties.state == 'play':
            await self.ampd.command_list([self.ampd.pause(1), self.ampd.disableoutput(output_id), self.ampd.enableoutput(output_id), self.ampd.pause(0)])
        else:
            await self.ampd.enableoutput(output_id)
            await self.ampd.command_list(self.ampd.disableoutput(output['outputid']) for output in self.outputs if output['outputid'] != output_id)
