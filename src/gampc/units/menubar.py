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


from gi.repository import Gio

from .. import util


class __unit__(util.unit.Unit):
    def __init__(self, name, manager):
        super().__init__(name, manager)

        self.require('window')

        self.families = self.unit_window.action_info_families = {}
        self.menubar = Gio.Menu()
        app = Gio.Application.get_default()
        app.set_menubar(self.menubar)

        app_menu = Gio.Menu()
        self.menubar.append_submenu(_("_Application"), app_menu)
        self.load_actions('persistent', _("Persistent"), app, app_menu, True)
        self.load_actions('window', _("_Window"), app, app_menu, True)
        self.load_actions('playback', _("_Playback"), app, self.menubar)
        self.load_actions('help', _("_Help"), app, self.menubar)

    def load_actions(self, unit_name, label, action_map, menu, section=False):
        unit = self.require(unit_name)
        family = self.families[unit_name] = util.action.ActionInfoFamily('app', label, unit.generate_actions())
        if section:
            menu.append_section(None, family.get_menu())
        else:
            menu.append_submenu(label, family.get_menu())
        family.add_to_action_map(action_map)
