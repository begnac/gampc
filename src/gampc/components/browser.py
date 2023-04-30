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


from . import treelist
from . import songlist


class Browser(treelist.TreeList, songlist.SongList):
    sortable = True

    left_title = _("Directory")

    def init_left_store(self):
        return self.unit.left_store

    async def get_node_songs(self, node):
        contents = await self.unit.get_path_contents(node.path)
        return contents.get('file', [])
