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
from ..util import dialog

from . import songlistbase
from . import songlist


NODE_FOLDER = 0
NODE_PLAYLIST = 1

PSEUDO_SEPARATOR = ' % '

ICONS = {
    NODE_FOLDER: 'folder-symbolic',
    NODE_PLAYLIST: 'view-list-symbolic',
}


class Playlist(songlistbase.SongListBasePaneMixin, songlistbase.SongListBaseEditStackMixin, songlist.SongListTotalsMixin, songlist.SongList):
    duplicate_test_columns = ['file']

    left_title = _("Playlists")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, editable=False, **kwargs)

        self.actions.add_action(resource.Action('rename', self.action_playlist_rename_cb))
        self.actions.add_action(resource.Action('delete', self.action_playlist_delete_cb))
        self.actions.add_action(resource.Action('update-from-queue', self.action_playlist_update_from_queue_cb))

    def edit_stack_changed(self):
        super().edit_stack_changed()
        if not self.editable:
            return
        if self.deltas and not self.left_selected_item.modified:
            self.left_selected_item.modified = True
        elif not self.deltas and self.left_selected_item.modified:
            self.left_selected_item.modified = False
        else:
            return
        pos = self.left_selected_item.parent_model.find(self.left_selected_item).position
        self.left_selected_item.parent_model.emit('items-changed', pos, 1, 1)

    def left_selection_changed_cb(self, selection, position, n_items):
        if self.editable:
            self.left_selected_item.delta_pos = self.delta_pos
            self.left_selected_item.records = list(self.view.record_store)
        super().left_selection_changed_cb(selection, position, n_items)
        self.view.record_store[:] = sum((selection[pos].get_item().records for pos in self.left_selected), [])
        if self.left_selected_item and self.left_selected_item.kind == NODE_PLAYLIST:
            self.deltas = self.left_selected_item.deltas
            self.delta_pos = self.left_selected_item.delta_pos
            self.editable = True
        else:
            self.deltas = []
            self.delta_pos = 0
            self.editable = False
        self.edit_stack_changed()

    def left_view_activate_cb(self, view, position):
        row = view.get_model()[position]
        node = row.get_item()
        if node.kind is NODE_FOLDER:
            super().left_view_activate_cb(view, position)
        else:
            self.action_playlist_rename_cb(None, None)

    @ampd.task
    async def action_save_cb(self, action, parameter):
        if not self.deltas:
            return
        if await self.unit.save_playlist(self.left_selected_item.joined_path, [record.file for record in self.view.record_store], self.widget.get_root()):
            self.deltas[:] = []
            self.delta_pos = 0
            self.edit_stack_changed()

    @ampd.task
    async def action_playlist_rename_cb(self, action, parameter):
        if not self.left_selected_item:
            return
        playlist_path = self.left_selected_item.joined_path
        await self.unit.rename_playlist(playlist_path, self.widget.get_root(), self.left_selected_item.kind == NODE_FOLDER)

    @ampd.task
    async def action_playlist_delete_cb(self, action, parameter):
        if not self.left_selected_item:
            return
        playlist_path = self.left_selected_item.joined_path
        if not await dialog.AsyncMessageDialog(transient_for=self.widget.get_root(), message=_("Delete playlist {name}?").format(name=playlist_path)).run():
            return
        await self.ampd.rm(playlist_path.replace('/', PSEUDO_SEPARATOR))

    @ampd.task
    async def action_playlist_update_from_queue_cb(self, action, parameter):
        if not self.selected_node:
            return
        playlist_path = self.selected_node.joined_path
        await self.unit.save_playlist(playlist_path, await self.ampd.playlist(), self.widget.get_root())
