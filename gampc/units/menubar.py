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


from gi.repository import Gio

from gampc.util import resource
from gampc.util import unit


class __unit__(unit.Unit):
    def __init__(self, name, manager):
        super().__init__(name, manager)

        self.new_resource_provider('app.menu').add_resources(
            resource.MenuPath('gampc', _("_GAMPC"), is_submenu=True),
            resource.MenuPath('edit', _("_Edit"), is_submenu=True),
            resource.MenuPath('playback', _("_Playback"), is_submenu=True),
            resource.MenuPath('server', _("_Server"), is_submenu=True),
            resource.MenuPath('modules', _("_Modules"), is_submenu=True),
            resource.MenuPath('help', _("_Help"), is_submenu=True),

            resource.MenuPath('gampc/window'),
            resource.MenuPath('gampc/persistent'),
            resource.MenuPath('gampc/app'),

            resource.MenuPath('edit/global'),
            resource.MenuPath('edit/module'),

            resource.MenuPath('server/server'),
            resource.MenuPath('server/profiles'),
        )

        self.new_resource_provider('app.user-action').add_resources(
            resource.UserAction('app.new-window', _("New window"), 'gampc/window', ['<Control>n']),
            resource.UserAction('app.close-window', _("Close window"), 'gampc/window', ['<Control>w']),
            resource.UserAction('win.toggle-fullscreen', _("Fullscreen window"), 'gampc/window', ['<Alt>f']),
            resource.UserAction('win.volume-popup', _("Adjust volume"), 'gampc/window', ['<Alt>v']),
            resource.UserAction('app.quit', _("Quit"), 'gampc/app', ['<Control>q']),
            resource.UserAction('app.BAD', "BAD", 'gampc/app', ['<Control><Alt>z']),

            resource.UserAction('app.help', _("Help"), 'help', ['<Control>h', 'F1']),
            resource.UserAction('app.about', _("About"), 'help'),
        )
