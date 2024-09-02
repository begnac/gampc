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
      columnview > listview > row > cell.duplicate-{d} {{
      background: rgba({colors[0]},{colors[1]},{colors[2]},0.5);
    }}
    '''


class __unit__(mixins.UnitConfigMixin, mixins.UnitCssMixin, unit.Unit):
    CSS = CSS
