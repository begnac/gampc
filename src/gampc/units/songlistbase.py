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

        items = [
            resource.MenuPath('edit/songlist'),
            resource.MenuPath('edit/songlist/base'),
            # resource.MenuAction('edit/songlist/base', 'mod.selectall', _("Select all"), ['<Control>a'], accels_fragile=True),
            resource.MenuAction('edit/songlist/base', 'songlistbase.cut', _("Cut"), ['<Control>x'], accels_fragile=True),
            resource.MenuAction('edit/songlist/base', 'songlistbase.copy', _("Copy"), ['<Control>c'], accels_fragile=True),
            resource.MenuAction('edit/songlist/base', 'songlistbase.paste', _("Paste"), ['<Control>v'], accels_fragile=True),
            resource.MenuAction('edit/songlist/base', 'songlistbase.paste-before', _("Paste before"), ['<Control>b']),
            resource.MenuAction('edit/songlist/base', 'songlistbase.delete', _("Delete"), ['Delete'], accels_fragile=True),
            resource.MenuAction('edit/songlist/base', 'songlistbase.undelete', _("Undelete"), ['<Alt>Delete'], accels_fragile=True),
        ]

        self.add_resources(
            'app.menu',
            resource.MenuAction('edit/global', 'songlistbase.save', _("Save"), ['<Control>s']),
            resource.MenuAction('edit/global', 'songlistbase.reset', _("Reset"), ['<Control>r']),
            resource.MenuAction('edit/global', 'songlistbase.filter', _("Filter"), ['<Control><Shift>f']),
            *items,
        )

        self.add_resources(
            'songlistbase.context.menu',
            resource.MenuPath('action'),
            resource.MenuPath('edit'),
            resource.MenuPath('other'),
            *items,
        )

        self.add_resources(
            'songlistbase.left-context.menu',
            resource.MenuPath('action'),
            resource.MenuPath('edit'),
            resource.MenuPath('other'),
        )
