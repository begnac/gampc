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
from ..ui import dialog

from . import itemlist
from . import songlist
from . import editstack


NODE_FOLDER = 0
NODE_PLAYLIST = 1

PSEUDO_SEPARATOR = ' % '

ICONS = {
    NODE_FOLDER: 'folder-symbolic',
    NODE_PLAYLIST: 'view-list-symbolic',
}


class Playlist(itemlist.ItemListTreeListMixin, editstack.ItemListEditStackFromCacheMixin, songlist.SongListTotalsMixin, songlist.SongList):
    duplicate_test_columns = ['file']

    left_title = _("Playlists")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, editable=False, **kwargs)

        self.actions.add_action(resource.Action('rename', self.action_playlist_rename_cb))
        self.actions.add_action(resource.Action('delete', self.action_playlist_delete_cb))
        self.actions.add_action(resource.Action('update-from-queue', self.action_playlist_update_from_queue_cb))

    def shutdown(self):
        self.set_edit_stack(None)
        super().shutdown()

    def edit_stack_changed(self):
        super().edit_stack_changed()
        if not self.get_editable():
            return
        if self.edit_stack.deltas and not self.left_selected_item.modified:
            self.left_selected_item.modified = True
        elif not self.edit_stack.deltas and self.left_selected_item.modified:
            self.left_selected_item.modified = False
        else:
            return
        pos = self.left_selected_item.parent_model.find(self.left_selected_item).position
        self.left_selected_item.parent_model.items_changed(pos, 1, 1)

    def left_selection_changed_cb(self, selection, position, n_items):
        super().left_selection_changed_cb(selection, position, n_items)
        if self.left_selected_item and self.left_selected_item.kind == NODE_PLAYLIST:
            self.set_edit_stack(self.left_selected_item.edit_stack)
            self.set_editable(True)
        else:
            self.set_edit_stack(None)
            self.set_editable(False)
            self.set_items(sum(map(lambda node: list(node.edit_stack.items),
                                   filter(lambda node: node.kind == NODE_PLAYLIST,
                                          map(lambda pos: selection[pos].get_item(),
                                              self.left_selection_pos))), []))
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
        if not self.edit_stack.deltas:
            return
        if await self.unit.save_playlist(self.left_selected_item.joined_path, [item.get_value() for item in self.view.item_store], self.widget.get_root()):
            self.edit_stack.reset()
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
