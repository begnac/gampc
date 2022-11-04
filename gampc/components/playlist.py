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


import ampd

from ..util import resource
from ..components import treelist
from ..components import songlist


NODE_FOLDER = 0
NODE_PLAYLIST = 1

PSEUDO_SEPARATOR = ' % '

ICONS = {
    NODE_FOLDER: 'folder-symbolic',
    NODE_PLAYLIST: 'view-list-symbolic',
}


class Playlist(songlist.SongListWithEditDelNew, songlist.SongListWithTotals, treelist.TreeList):
    title = _("Playlists")
    name = 'playlist'
    key = '5'

    duplicate_test_columns = ['file']

    left_title = _("Playlists")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.actions.add_action(resource.Action('playlist-rename', self.action_playlist_rename_cb))
        self.actions.add_action(resource.Action('playlist-delete', self.action_playlist_delete_cb))
        self.actions.add_action(resource.Action('playlist-update-from-queue', self.action_playlist_update_from_queue_cb))

    def init_left_store(self):
        return self.unit.left_store

    async def get_node_songs(self, node):
        if node.kind == NODE_FOLDER:
            return []
        elif node.modified:
            return node.songs
        else:
            return await self.ampd.listplaylistinfo(PSEUDO_SEPARATOR.join(node.path))

    @ampd.task
    async def left_treeview_selection_changed_cb(self, *args):
        if self.selected_node is not None and self.selected_node.modified:
            self.selected_node.songs = [song.get_data() for i, p, song in self.store]
        await super().left_treeview_selection_changed_cb(*args)
        self.set_editable(self.selected_node is not None and self.selected_node.kind == NODE_PLAYLIST)

    def left_treeview_row_activated_cb(self, left_treeview, p, col):
        node = self.left_store.get_node(self.left_store.get_iter(p))
        if node.kind is NODE_FOLDER:
            super().left_treeview_row_activated_cb(left_treeview, p, col)
        else:
            self.action_playlist_rename_cb(None, None)

    def set_modified(self, modified=True):
        if self.selected_node is None or self.selected_node.kind != NODE_PLAYLIST:
            return
        self.selected_node.modified = modified
        if modified:
            self.selected_node.songs = [song.get_data() for i, p, song in self.store]
        else:
            del self.selected_node.songs
        self.left_treeview.queue_draw()
        self.treeview.queue_draw()

    @ampd.task
    async def action_reset_cb(self, action, parameter):
        super().action_reset_cb(action, parameter)
        self.set_modified(False)
        await self.left_treeview_selection_changed_cb()

    @ampd.task
    async def action_save_cb(self, action, parameter):
        if self.selected_node is None or not self.selected_node.modified:
            return
        records = [song for i, p, song in self.store if song._status != self.RECORD_DELETED]
        result = await self.unit.save_playlist(self.selected_node.joined_path, [record.file for record in records], self.win)
        if result:
            self.treeview.get_selection().unselect_all()
            super().left_treeview_selection_changed_cb()
            self.set_modified(False)

    @ampd.task
    async def action_playlist_rename_cb(self, action, parameter):
        if not self.selected_node:
            return
        playlist_path = self.selected_node.joined_path
        await self.unit.rename_playlist(playlist_path, self.win, self.selected_node.kind == NODE_FOLDER)

    @ampd.task
    async def action_playlist_delete_cb(self, action, parameter):
        if not self.selected_node:
            return
        playlist_path = self.selected_node.joined_path
        if not await self.unit.confirm(self.win, _("Delete playlist {name}?").format(name=playlist_path)):
            return
        await self.ampd.rm(playlist_path.replace('/', PSEUDO_SEPARATOR))

    @ampd.task
    async def action_playlist_update_from_queue_cb(self, action, parameter):
        if not self.selected_node:
            return
        playlist_path = self.selected_node.joined_path
        await self.unit.save_playlist(playlist_path, await self.ampd.playlist(), self.win)
