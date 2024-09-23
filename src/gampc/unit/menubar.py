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

from ..util import action
from ..util import unit


class __unit__(unit.Unit):
    def __init__(self, manager):
        super().__init__(manager)

        self.require('window')
        self.require('persistent')
        self.require('playback')
        self.require('server')
        self.require('output')
        self.require('profiles')
        self.require('component')
        self.require('help')

        self.action_info_families = self.unit_window.action_info_families = []
        self.menubar = self.unit_window.menubar = Gio.Menu()
        app = Gio.Application.get_default()
        app.set_menubar(self.menubar)

        app_menu = Gio.Menu()
        app_label = _("_Application")
        self.menubar.append_submenu(app_label, app_menu)
        self.load_family(self.unit_window.generate_actions(), app_label, app, app_menu, True)
        self.load_family(self.unit_persistent.generate_actions(), app_label, app, app_menu, True)
        quit_action = action.ActionInfo('quit', self.quit_cb, _("Quit"), ['<Control>q'])
        self.load_family([quit_action], app_label, app, app_menu, True)

        self.load_family(self.unit_playback.generate_actions(), _("_Playback"), app, self.menubar)

        server_menu = Gio.Menu()
        server_label = _("_Server")
        self.menubar.append_submenu(server_label, server_menu)
        self.load_family(self.unit_server.generate_database_actions(), server_label, app, server_menu, True)
        app.follow_action_group(self.unit_output.actions)
        server_menu.append_section(None, self.unit_output.menu)
        self.load_family(self.unit_server.generate_connection_actions(), server_label, app, server_menu, True)
        server_menu.append_submenu(_("Profiles"), self.unit_profiles.menu)

        component_label = _("_Component")
        self.menubar.append_submenu(component_label, self.unit_component.menu)
        self.action_info_families.append(self.unit_component.start_family)
        self.action_info_families.append(self.unit_component.stop_family)
        self.unit_component.start_family.add_to_action_map(app)
        self.unit_component.stop_family.add_to_action_map(app)

        self.load_family(self.unit_help.generate_actions(), _("_Help"), app, self.menubar)

    def cleanup(self):
        self.action_info_families.clear()
        super().cleanup()

    def load_family(self, generator, label, action_map, menu, section=False):
        family = action.ActionInfoFamily(generator, 'app', label)
        self.action_info_families.append(family)
        if section:
            menu.append_section(None, family.get_menu())
        else:
            menu.append_submenu(label, family.get_menu())
        family.add_to_action_map(action_map, protect=self.unit_persistent.protect)

    @staticmethod
    def quit_cb(action, parameter):
        Gio.Application.get_default().quit()
