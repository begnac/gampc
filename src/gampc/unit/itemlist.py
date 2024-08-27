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


from ..util import unit

from ..ui import dnd

from . import mixins


CSS = ''

CSS += '''
columnview.filter > listview > row {
  background: yellow;
}
'''

CSS += dnd.CSS

N = 4
for d in range(N ** 3):
    colors = [((d // (N ** k)) % N) * 255 / (N - 1) for k in range(3)]
    CSS += f'''
      columnview.itemlist > listview > row > cell.duplicate-{d} {{
      background: rgba({colors[0]},{colors[1]},{colors[2]},0.5);
    }}
    '''


class __unit__(mixins.UnitConfigMixin, mixins.UnitCssMixin, unit.Unit):
    CSS = CSS

    def xxxx__init__(self, *args):
        super().__init__(*args)

        items = [
            # util.resource.MenuAction('edit/songlist/base', 'itemlist.undo', _("Undo"), ['<Control>z'], accels_fragile=True),
            # util.resource.MenuAction('edit/songlist/base', 'itemlist.redo', _("Redo"), ['<Shift><Control>z'], accels_fragile=True),
            # util.resource.MenuAction('edit/songlist/base', 'itemlist.undelete', _("Undelete"), ['<Alt>Delete'], accels_fragile=True),
        ]

        # self.add_resources(
        #     'app.menu',
        #     util.resource.MenuAction('edit/global', 'itemlist.save', _("Save"), ['<Control>s']),
        #     util.resource.MenuAction('edit/global', 'itemlist.reset', _("Reset"), ['<Control>r']),
        #     *items,
        # )

        # self.add_resources(
        #     'itemlist.context.menu',
        #     util.resource.MenuPath('action'),
        #     util.resource.MenuPath('edit'),
        #     util.resource.MenuPath('other'),
        #     *items,
        # )

        # self.add_resources(
        #     'itemlist.left-context.menu',
        #     util.resource.MenuPath('action'),
        #     util.resource.MenuPath('edit'),
        #     util.resource.MenuPath('other'),
        # )
