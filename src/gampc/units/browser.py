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


from gi.repository import Gtk

import os

import ampd

from ..util import unit
from ..ui import treelist
from ..components import songlistbase
from ..components import songlist


DIRECTORY = 'directory'


class Browser(songlistbase.SongListBaseTreeListMixin, songlist.SongList):
    sortable = True

    @ampd.task
    async def client_connected_cb(self, client):
        while True:
            self.root.update(self.unit.fill_node)
            self.root.expose()
            await self.root.updated
            await self.root.sub_nodes[0].updated
            self.left_selection[0].set_expanded(True)
            await self.ampd.idle(ampd.DATABASE)
            self.root.reset()

    def left_selection_changed_cb(self, selection, position, n_items):
        super().left_selection_changed_cb(selection, position, n_items)
        self.set_songs(sum((selection[pos].get_item().songs for pos in self.left_selection_pos), []))


class __unit__(songlist.UnitPanedSongListMixin, unit.Unit):
    title = _("Database Browser")
    key = '2'

    COMPONENT_CLASS = Browser

    @staticmethod
    def new_root():
        return treelist.TreeNode(parent_model=None)

    async def fill_node(self, node):
        if node.path:
            contents = await self.ampd.lsinfo('/'.join(node.path[1:]))
        else:
            contents = {DIRECTORY: [{DIRECTORY: _("Music")}]}
        for folder in sorted(os.path.basename(item[DIRECTORY]) for item in contents.get(DIRECTORY, [])):
            node.append_sub_node(treelist.TreeNode(name=folder, path=node.path, icon='folder-symbolic'))
        node.songs = contents.get('file', [])
