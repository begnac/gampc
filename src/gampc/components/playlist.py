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

from ..ui import compound
from ..ui import dialog

from ..view.key import ViewWithCopyPasteEditStackSong

from . import songlist


NODE_FOLDER = 0
NODE_PLAYLIST = 1

PSEUDO_SEPARATOR = ' % '

ICONS = {
    NODE_FOLDER: 'folder-symbolic',
    NODE_PLAYLIST: 'view-list-symbolic',
}


class PlaylistWidget(compound.WidgetWithPanedTreeList):
    def left_selection_changed_cb(self, selection, position, n_items):
        super().left_selection_changed_cb(selection, position, n_items)
        if self.left_selected_item and self.left_selected_item.kind == NODE_PLAYLIST:
            self.main.set_edit_stack(self.left_selected_item.edit_stack)
            self.main.set_editable(True)
        else:
            self.main.set_edit_stack(None)
            self.main.set_editable(False)
            self.main.set_keys(sum(map(lambda node: list(node.edit_stack.items),
                                       filter(lambda node: node.kind == NODE_PLAYLIST,
                                              map(lambda pos: selection[pos].get_item(),
                                                  self.left_selection_pos))), []))
        self.main.edit_stack_changed()

    @staticmethod
    def left_view_activate_cb(view, position):
        row = view.get_model()[position]
        node = row.get_item()
        if node.kind is NODE_FOLDER:
            compound.WidgetWithPanedTreeList.left_view_activate_cb(view, position)
        else:  # XXXXXXXXXXXXXX
            self.action_playlist_rename_cb(None, None)


class Playlist(songlist.SongListTotalsMixin, songlist.SongList):
    duplicate_test_columns = ['file']

    def __init__(self, unit):
        super().__init__(unit)
        self.widget = PlaylistWidget(self.view, self.config.pane_separator, unit.root.model)

        # self.actions.add_action(resource.Action('rename', self.action_playlist_rename_cb))
        # self.actions.add_action(resource.Action('delete', self.action_playlist_delete_cb))
        # self.actions.add_action(resource.Action('update-from-queue', self.action_playlist_update_from_queue_cb))

        self.view.connect('edit-stack-changed', self.edit_stack_changed_cb)

    def create_view(self, *args, **kwargs):
        return ViewWithCopyPasteEditStackSong(*args, **kwargs, separator_file=self.unit.unit_database.SEPARATOR_FILE, cache=self.unit.unit_database.cache)

    @staticmethod
    def edit_stack_changed_cb(view):
        if not view.get_editable():
            return
        widget = view.get_parent()
        if view.edit_stack.deltas and not widget.left_selected_item.modified:
            widget.left_selected_item.modified = True
        elif not view.edit_stack.deltas and widget.left_selected_item.modified:
            widget.left_selected_item.modified = False
        else:
            return
        pos = widget.left_selected_item.parent_model.find(widget.left_selected_item).position
        widget.left_selected_item.parent_model.items_changed(pos, 1, 1)

    @ampd.task
    async def action_save_cb(self, action, parameter):
        if not self.edit_stack.deltas:
            return
        if await self.unit.save_playlist(self.left_selected_item.joined_path, [item.get_key() for item in self.view.item_store], self.widget.get_root()):
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
        if not await dialog.MessageDialogAsync(transient_for=self.widget.get_root(), message=_("Delete playlist {name}?").format(name=playlist_path)).run():
            return
        await self.ampd.rm(playlist_path.replace('/', PSEUDO_SEPARATOR))

    @ampd.task
    async def action_playlist_update_from_queue_cb(self, action, parameter):
        if not self.selected_node:
            return
        playlist_path = self.selected_node.joined_path
        await self.unit.save_playlist(playlist_path, await self.ampd.playlist(), self.widget.get_root())
