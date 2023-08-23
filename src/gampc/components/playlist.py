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


import ampd

from ..util import resource

from . import songlistbase
from . import songlist


NODE_FOLDER = 0
NODE_PLAYLIST = 1

PSEUDO_SEPARATOR = ' % '

ICONS = {
    NODE_FOLDER: 'folder-symbolic',
    NODE_PLAYLIST: 'view-list-symbolic',
}


class Playlist(songlistbase.SongListBaseEditStackMixin, songlistbase.SongListBasePaneMixin, songlist.SongListTotalsMixin, songlist.SongList):
    duplicate_test_columns = ['file']

    left_title = _("Playlists")

    def __init__(self, *args, **kwargs):
        self.edit_node = None

        super().__init__(*args, **kwargs)

        self.actions.add_action(resource.Action('rename', self.action_playlist_rename_cb))
        self.actions.add_action(resource.Action('delete', self.action_playlist_delete_cb))
        self.actions.add_action(resource.Action('update-from-queue', self.action_playlist_update_from_queue_cb))

    def edit_stack_changed(self):
        super().edit_stack_changed()
        if self.deltas and not self.edit_node.modified:
            self.edit_node.modified = True
        elif not self.deltas and self.edit_node.modified:
            self.edit_node.modified = False
        else:
            return
        pos = self.edit_node.parent_model.find(self.edit_node).position
        self.edit_node.parent_model.emit('items-changed', pos, 1, 1)

    def left_selection_changed_cb(self, selection, position, n_items):
        if self.edit_node is not None:
            self.edit_node.delta_pos = self.delta_pos
            self.edit_node.records = list(self.view.record_store)
        super().left_selection_changed_cb(selection, position, n_items)
        self.view.record_store[:] = sum((selection[pos].get_item().records for pos in self.left_selected), [])
        self.edit_node = None
        if len(self.left_selected) == 1:
            node = selection[self.left_selected[0]].get_item()
            if node.kind == NODE_PLAYLIST:
                self.edit_node = node
                self.deltas = node.deltas
                self.delta_pos = node.delta_pos
        self.set_editable(self.edit_node is not None)

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
        result = await self.unit.save_playlist(self.selected_node.joined_path, [record.file for record in records], self.widget.get_toplevel())
        if result:
            self.treeview.get_selection().unselect_all()
            super().left_treeview_selection_changed_cb()
            self.set_modified(False)

    @ampd.task
    async def action_playlist_rename_cb(self, action, parameter):
        if not self.selected_node:
            return
        playlist_path = self.selected_node.joined_path
        await self.unit.rename_playlist(playlist_path, self.widget.get_toplevel(), self.selected_node.kind == NODE_FOLDER)

    @ampd.task
    async def action_playlist_delete_cb(self, action, parameter):
        if not self.selected_node:
            return
        playlist_path = self.selected_node.joined_path
        if not await self.unit.confirm(self.widget.get_toplevel(), _("Delete playlist {name}?").format(name=playlist_path)):
            return
        await self.ampd.rm(playlist_path.replace('/', PSEUDO_SEPARATOR))

    @ampd.task
    async def action_playlist_update_from_queue_cb(self, action, parameter):
        if not self.selected_node:
            return
        playlist_path = self.selected_node.joined_path
        await self.unit.save_playlist(playlist_path, await self.ampd.playlist(), self.widget.get_toplevel())
