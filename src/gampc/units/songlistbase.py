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


class __unit__(unit.UnitMixinConfig, unit.Unit):
    def __init__(self, name, manager):
        super().__init__(name, manager)

        menus = [
            resource.MenuPath('edit/songlist'),
            resource.MenuPath('edit/songlist/base'),
        ]

        actions = [
            # resource.MenuAction('edit/songlist/base', 'mod.selectall', _("Select all"), ['<Control>a'], accels_fragile=True),
            resource.MenuAction('edit/songlist/base', 'mod.cut', _("Cut"), ['<Control>x'], accels_fragile=True),
            resource.MenuAction('edit/songlist/base', 'mod.copy', _("Copy"), ['<Control>c'], accels_fragile=True),
            resource.MenuAction('edit/songlist/base', 'mod.paste', _("Paste"), ['<Control>v'], accels_fragile=True),
            resource.MenuAction('edit/songlist/base', 'mod.paste-before', _("Paste before"), ['<Control>b']),
            resource.MenuAction('edit/songlist/base', 'mod.delete', _("Delete"), ['Delete'], accels_fragile=True),
            resource.MenuAction('edit/songlist/base', 'mod.undelete', _("Undelete"), ['<Alt>Delete'], accels_fragile=True),
        ]

        self.add_resources(
            'app.menu',
            *menus,
            resource.MenuAction('edit/global', 'mod.save', _("Save"), ['<Control>s']),
            resource.MenuAction('edit/global', 'mod.reset', _("Reset"), ['<Control>r']),
            resource.MenuAction('edit/global', 'mod.filter', _("Filter"), ['<Control><Shift>f']),
            *actions,
        )

        self.add_resources(
            'songlistbase.context.menu',
            resource.MenuPath('action'),
            resource.MenuPath('edit'),
            *menus,
            resource.MenuPath('other'),
            *actions,
        )

        self.add_resources(
            'songlistbase.left-context.menu',
            resource.MenuPath('action'),
            resource.MenuPath('edit'),
            resource.MenuPath('other'),
        )
