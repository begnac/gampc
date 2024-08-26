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


from .. import util
from .. import ui


CSS = ''

CSS += '''
columnview.filter > listview > row {
  background: yellow;
}
'''

CSS += ui.dnd.CSS

N = 4
for d in range(N ** 3):
    colors = [((d // (N ** k)) % N) * 255 / (N - 1) for k in range(3)]
    CSS += f'''
      columnview.itemlist > listview > row > cell.duplicate-{d} {{
      background: rgba({colors[0]},{colors[1]},{colors[2]},0.5);
    }}
    '''


class __unit__(util.unit.UnitConfigMixin, util.unit.UnitCssMixin, util.unit.Unit):
    CSS = CSS

    def __init__(self, name, manager):
        super().__init__(name, manager)

        items = [
            util.resource.MenuPath('edit/songlist'),
            util.resource.MenuPath('edit/songlist/base'),
            # util.resource.MenuAction('edit/songlist/base', 'mod.selectall', _("Select all"), ['<Control>a'], accels_fragile=True),
            # util.resource.MenuAction('edit/songlist/base', 'itemlist.cut', _("Cut"), ['<Control>x'], accels_fragile=True),
            # util.resource.MenuAction('edit/songlist/base', 'itemlist.copy', _("Copy"), ['<Control>c'], accels_fragile=True),
            # util.resource.MenuAction('edit/songlist/base', 'itemlist.paste', _("Paste"), ['<Control>v'], accels_fragile=True),
            # util.resource.MenuAction('edit/songlist/base', 'itemlist.paste-before', _("Paste before"), ['<Control>b']),
            # util.resource.MenuAction('edit/songlist/base', 'itemlist.delete', _("Delete"), ['Delete'], accels_fragile=True),
            # util.resource.MenuAction('edit/songlist/base', 'itemlist.undo', _("Undo"), ['<Control>z'], accels_fragile=True),
            # util.resource.MenuAction('edit/songlist/base', 'itemlist.redo', _("Redo"), ['<Shift><Control>z'], accels_fragile=True),
            # util.resource.MenuAction('edit/songlist/base', 'itemlist.undelete', _("Undelete"), ['<Alt>Delete'], accels_fragile=True),
        ]

        self.add_resources(
            'app.menu',
            util.resource.MenuAction('edit/global', 'itemlist.save', _("Save"), ['<Control>s']),
            util.resource.MenuAction('edit/global', 'itemlist.reset', _("Reset"), ['<Control>r']),
            util.resource.MenuAction('edit/global', 'itemlist.filter', _("Filter"), ['<Control><Shift>f']),
            *items,
        )

        self.add_resources(
            'itemlist.context.menu',
            util.resource.MenuPath('action'),
            util.resource.MenuPath('edit'),
            util.resource.MenuPath('other'),
            *items,
        )

        self.add_resources(
            'itemlist.left-context.menu',
            util.resource.MenuPath('action'),
            util.resource.MenuPath('edit'),
            util.resource.MenuPath('other'),
        )
