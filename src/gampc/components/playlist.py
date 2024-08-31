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


from ..util import action
from ..util import item
from ..util import misc

from ..ui import compound

from ..view.cache import ViewWithCopyPasteEditStackSong

from . import songlist


NODE_FOLDER = 0
NODE_PLAYLIST = 1

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
    def left_view_activate_cb(left_view, position):
        row = left_view.get_model()[position]
        node = row.get_item()
        if node.kind is NODE_FOLDER:
            compound.WidgetWithPanedTreeList.left_view_activate_cb(left_view, position)
        else:
            left_view.activate_action('playlist-global.rename')


class Playlist(songlist.SongListTotalsMixin, songlist.SongList):
    def __init__(self, unit):
        super().__init__(unit, ViewWithCopyPasteEditStackSong(fields=unit.unit_fields.fields, separator_file=unit.unit_database.SEPARATOR_FILE, cache=unit.unit_database.cache))
        self.widget = PlaylistWidget(self.view, self.config.pane_separator, unit.root.model)

        self.view.connect('edit-stack-changed', self.edit_stack_changed_cb)
        item.setup_find_duplicate_items(self.view.item_store, ['file'], [self.unit.unit_database.SEPARATOR_FILE])

        self.view.add_to_context_menu(self.generate_actions(), 'playlist-local', _("Playlist"), below='edit-stack')
        self.widget.add_to_context_menu(self.generate_left_actions(), 'playlist-global', _("Playlist global"))

    def generate_actions(self):
        yield action.ActionInfo('save', self.global_action_cb, _("Save"), ['<Control>s'])

    def generate_left_actions(self):
        yield from self.generate_actions()
        yield action.ActionInfo('rename', self.global_action_cb, _("Rename"))
        yield action.ActionInfo('delete', self.global_action_cb, _("Delete"))
        yield action.ActionInfo('update-from-queue', self.global_action_cb, _("Update from play queue"))

    @misc.create_task
    async def global_action_cb(self, action, parameter):
        if not self.widget.left_selected_item:
            return
        path = self.widget.left_selected_item.joined_path
        window = self.widget.get_root()
        if action.get_name() == 'save':
            if not self.view.edit_stack.transactions:
                return
            if await self.unit.save_playlist(window, path, [item.get_key() for item in self.view.item_store]):
                self.view.edit_stack.reset()
                self.view.edit_stack_changed()
        elif action.get_name() == 'rename':
            await self.unit.rename_playlist(window, path, self.widget.left_selected_item.kind == NODE_FOLDER)
        elif action.get_name() == 'delete':
            await self.unit.delete_playlist(window, path)
        elif action.get_name() == 'update-from-queue':
            await self.unit.save_playlist(window, path, await self.ampd.playlist())
        else:
            raise RuntimeError

    @staticmethod
    def edit_stack_changed_cb(view):
        if not view.get_editable():
            return
        widget = view.get_parent()
        if view.edit_stack.index and not widget.left_selected_item.modified:
            widget.left_selected_item.modified = True
        elif not view.edit_stack.index and widget.left_selected_item.modified:
            widget.left_selected_item.modified = False
        else:
            return
        pos = widget.left_selected_item.parent_model.find(widget.left_selected_item).position
        widget.left_selected_item.parent_model.items_changed(pos, 1, 1)
