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


from ..util import resource
from ..util import unit


class __unit__(unit.Unit):
    def __init__(self, name, manager):
        super().__init__(name, manager)

        self.add_resources(
            'app.menu',
            resource.MenuPath('gampc', _("_GAMPC"), is_submenu=True),
            resource.MenuPath('edit', _("_Edit"), is_submenu=True),
            resource.MenuPath('playback', _("_Playback"), is_submenu=True),
            resource.MenuPath('server', _("_Server"), is_submenu=True),
            resource.MenuPath('components', _("_Components"), is_submenu=True),
            resource.MenuPath('help', _("_Help"), is_submenu=True),

            resource.MenuPath('gampc/window'),
            resource.MenuPath('gampc/persistent'),
            resource.MenuPath('gampc/app'),

            resource.MenuPath('edit/global'),
            resource.MenuPath('edit/component'),

            resource.MenuPath('server/server'),
            resource.MenuPath('server/profiles'),

            resource.MenuAction('gampc/window', 'app.new-window', _("New window"), ['<Control>n']),
            resource.MenuAction('gampc/window', 'app.close-window', _("Close window"), ['<Control>w']),
            resource.MenuAction('gampc/window', 'win.toggle-fullscreen', _("Fullscreen window"), ['<Alt>f']),
            resource.MenuAction('gampc/window', 'win.volume-popup', _("Adjust volume"), ['<Alt>v']),
            resource.MenuAction('gampc/app', 'app.quit', _("Quit"), ['<Control>q']),

            resource.MenuAction('help', 'app.help', _("Help"), ['<Control>h', 'F1']),
            resource.MenuAction('help', 'app.about', _("About")),
        )
