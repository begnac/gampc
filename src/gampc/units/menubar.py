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
    def __init__(self, *args):
        super().__init__(*args)

        self.require('window')

        self.unit_window.action_info_families = []
        self.menubar = Gio.Menu()
        app = Gio.Application.get_default()
        app.set_menubar(self.menubar)

        app_menu = Gio.Menu()
        app_label = _("_Application")
        self.menubar.append_submenu(app_label, app_menu)
        self.load_unit_family('window', app_label, app, app_menu, True)
        self.load_unit_family('persistent', app_label, app, app_menu, True)
        quit_action = util.action.ActionInfo('quit', self.quit_cb, _("Quit"), ['<Control>q'])
        self.load_family([quit_action], app_label, app, app_menu, True)

        self.load_unit_family('playback', _("_Playback"), app, self.menubar)

        server_menu = Gio.Menu()
        server_label = _("_Server")
        self.menubar.append_submenu(server_label, server_menu)
        unit_server = self.require('server')
        self.load_family(unit_server.generate_database_actions(), server_label, app, server_menu, True)
        self.load_unit_simple('output', app, server_menu)
        self.load_family(unit_server.generate_connection_actions(), server_label, app, server_menu, True)
        unit_profiles = self.require('profiles')
        server_menu.append_submenu(_("Profiles"), unit_profiles.menu)

        self.load_unit_family('help', _("_Help"), app, self.menubar)

    def load_unit_family(self, unit_name, label, action_map, menu, section=False):
        self.load_family(self.require(unit_name).generate_actions(), label, action_map, menu, section)

    def load_family(self, generator, label, action_map, menu, section=False):
        family = util.action.ActionInfoFamily('app', label, generator)
        self.unit_window.action_info_families.append(family)
        if section:
            menu.append_section(None, family.get_menu())
        else:
            menu.append_submenu(label, family.get_menu())
        family.add_to_action_map(action_map)

    def load_unit_simple(self, unit_name, app, menu):
        unit = self.require(unit_name)
        app.follow_action_group(unit.actions)
        menu.append_section(None, unit.menu)

    @staticmethod
    def quit_cb(action, parameter):
        Gio.Application.get_default().quit()
