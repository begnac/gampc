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

import ampd

from ..util import action
from ..util import cache
from ..util import cleanup
from ..util import item
from ..util import misc
from ..util import unit

from ..ui import dialog
from ..ui import treelist

from ..view.cache import ViewCacheWithCopyPasteSong

from ..control import compound
from ..control import editstack

from . import mixins


NODE_FOLDER = 0
NODE_PLAYLIST = 1

ICONS = {
    NODE_FOLDER: 'folder-symbolic',
    NODE_PLAYLIST: 'view-list-symbolic',
}


class PlaylistWidget(editstack.WidgetCacheEditStackMixin, compound.WidgetWithPanedTreeList):
    def __init__(self, fields, separator_file, cache, config, root_model):
        main = ViewCacheWithCopyPasteSong(fields=fields, separator_file=separator_file, cache=cache)
        super().__init__(main, config, root_model, edit_stack_view=main)
        self.add_cleanup_below(main)

        self.main.context_menu.append_section(None, self.edit_stack_menu)
        self.context_menu.append_section(None, self.edit_stack_menu)
        self.edit_stack_splicer = self.main.splice_keys

        item.setup_find_duplicate_items(main.item_model, ['file'], [separator_file])

    def action_save_cb(self, action, parameter):
        self.activate_action('playlist.save')

    def edit_stack_changed(self):
        super().edit_stack_changed()
        item = self.left_selected_item
        if item is None:
            return
        pos = item.parent_model.find(item).position
        item.parent_model.items_changed(pos, 1, 1)

    def left_selection_changed_cb(self, selection, position, n_items):
        super().left_selection_changed_cb(selection, position, n_items)
        if self.left_selected_item and self.left_selected_item.kind == NODE_PLAYLIST:
            self.main.set_editable(True)
            self.set_edit_stack(self.left_selected_item.edit_stack)
        else:
            self.main.set_editable(False)
            self.set_edit_stack(None)
            self.main.set_keys(sum(map(lambda node: list(node.edit_stack.frozen),
                                       filter(lambda node: node.kind == NODE_PLAYLIST,
                                              map(lambda pos: selection[pos].get_item(),
                                                  self.left_selection_pos))), []))

    @staticmethod
    def left_view_activate_cb(left_view, position):
        row = left_view.get_model()[position]
        node = row.get_item()
        if node.kind is NODE_FOLDER:
            compound.WidgetWithPanedTreeList.left_view_activate_cb(left_view, position)
        else:
            left_view.activate_action('playlist-global.rename')


class PlaylistCacheItem:
    def __init__(self, files, last_modified):
        self.files = files
        self.last_modified = last_modified


class ChoosePathDialog(dialog.TextDialogAsync):
    def __init__(self, *args, paths, init=None, path_ok=False, **kwargs):
        super().__init__(*args, text=init, **kwargs)
        self.paths = list(paths)
        self.path_ok = path_ok

        self.entry.connect('activate', self.entry_activate_cb)

        model = Gtk.ListStore(str)
        for p in self.paths:
            i = model.append()
            model.set_value(i, 0, p)

        completion = Gtk.EntryCompletion(model=model, text_column=0, inline_completion=True, inline_selection=True)
        completion.set_match_func(self.match_func)
        self.entry.set_completion(completion)

        cell = Gtk.CellRendererText()
        completion.get_area().add(cell)
        completion.get_area().attribute_connect(cell, 'text', 0)

    @staticmethod
    def match_func(completion, key, i):
        key = completion.get_entry().get_text().lower()
        line = completion.get_model().get_value(i, 0).lower()
        if line.startswith(key) and '/' not in line[len(key):-1]:
            return True
        else:
            return False

    @staticmethod
    def entry_activate_cb(entry):
        entry.get_completion().complete()

    def validate_text(self, text):
        if not text or (text + '/') in self.paths:
            return False
        if not self.path_ok and text.endswith('/'):
            return False
        return True


class __unit__(cleanup.CleanupCssMixin, mixins.UnitComponentQueueActionMixin, mixins.UnitComponentTandaActionMixin, mixins.UnitConfigMixin, unit.Unit):
    TITLE = _("Playlist")
    KEY = '5'

    PSEUDO_SEPARATOR = ' % '
    TEMPNAME = '$$TEMP$$'

    CSS = """
    listview > row > treeexpander > box > label.modified {
      font-style: italic;
      font-weight: bold;
    }
    """

    def __init__(self, manager):
        super().__init__(manager)
        self.config.pane_separator._get(default=100)
        self.require('database')
        self.require('fields')
        self.require('persistent')

        self.css_provider.load_from_string(self.CSS)

        self.playlist_cache = cache.AsyncCache(self.playlist_retrieve)
        self.playlists = {}
        self.root = treelist.TreeNode(kind=NODE_FOLDER, parent_model=None, fill_sub_nodes_cb=lambda node: self.fill_sub_nodes_cb(node), fill_contents_cb=self.fill_contents_cb)

    def cleanup(self):
        super().cleanup()
        del self.root
        del self.playlist_cache

    def new_widget(self):
        playlist = PlaylistWidget(self.unit_fields.fields, self.unit_database.SEPARATOR_FILE, self.unit_database.cache, self.config.pane_separator, self.root.model)
        view = playlist.main

        view.add_context_menu_actions(self.generate_queue_actions(view), 'queue', self.TITLE, protect=self.unit_persistent.protect)
        view.add_context_menu_actions(self.generate_tanda_actions(view), 'tanda', self.TITLE)

        playlist.add_context_menu_actions(self.generate_playlist_actions(playlist), 'playlist', self.TITLE)
        playlist.add_context_menu_actions(self.generate_queue_actions(view, False), 'queue', self.TITLE, protect=self.unit_persistent.protect)

        playlist.connect_clean(view.item_view, 'activate', self.view_activate_cb)

        return playlist

    @ampd.task
    async def client_connected_cb(self, client):
        try:
            while True:
                self.playlists = {entry['playlist']: entry['Last_Modified'] for entry in await self.ampd.listplaylists() if entry['playlist'] != self.TEMPNAME}
                for name, value in list(self.playlist_cache.items()):
                    if value.last_modified != self.playlists.get(name):
                        self.playlist_cache.pop(name)
                self.root.reset()
                await self.root.fill_sub_nodes()
                self.root.expose()
                await self.ampd.idle(ampd.STORED_PLAYLIST)
        finally:
            self.playlists = {}

    async def playlist_retrieve(self, name):
        files = await self.ampd.listplaylist(name)
        return PlaylistCacheItem(files, self.playlists[name])

    async def fill_sub_nodes_cb(self, node):
        if node.kind == NODE_FOLDER:
            folders, playlists = self.get_pseudo_folder_contents(node.path)
            for name in folders:
                node.append_sub_node(treelist.TreeNode(name=name, path=node.path, icon=ICONS[NODE_FOLDER], kind=NODE_FOLDER))
            for name in playlists:
                node.append_sub_node(treelist.TreeNode(name=name, path=node.path, icon=ICONS[NODE_PLAYLIST], kind=NODE_PLAYLIST))

    async def fill_contents_cb(self, node):
        if node.kind == NODE_PLAYLIST:
            item = await self.playlist_cache.get_async(self.PSEUDO_SEPARATOR.join(node.path))
            node.edit_stack = editstack.EditStack(item.files)

    def get_pseudo_folder_contents(self, path):
        prefix = ''.join(folder + self.PSEUDO_SEPARATOR for folder in path)
        folders = []
        names = []

        last_folder = None

        for name in sorted(self.playlists.keys()):
            if not name.startswith(prefix):
                continue
            name = name[len(prefix):]
            if self.PSEUDO_SEPARATOR in name:
                folder_name = name.split(self.PSEUDO_SEPARATOR, 1)[0]
                if folder_name != last_folder:
                    last_folder = folder_name
                    folders.append(folder_name)
            else:
                names.append(name)

        return folders, names

    def playlist_paths(self):
        last_path = []
        for playlist_name in sorted(self.playlists):
            playlist_path = playlist_name.split(self.PSEUDO_SEPARATOR)
            common = min(len(last_path), len(playlist_path) - 1)
            for i in range(common):
                if last_path[i] != playlist_path[i]:
                    common = i
                    break
            last_path = last_path[:common]
            for element in playlist_path[common:-1]:
                last_path.append(element)
                yield '/'.join(last_path) + '/'
            yield '/'.join(playlist_path)

    def generate_playlist_actions(self, widget):
        yield action.ActionInfo('save', self.global_action_cb, activate_args=(widget,))
        yield action.ActionInfo('rename', self.global_action_cb, _("Rename"), activate_args=(widget,))
        yield action.ActionInfo('delete', self.global_action_cb, _("Delete"), activate_args=(widget,))
        yield action.ActionInfo('update-from-queue', self.global_action_cb, _("Update from play queue"), activate_args=(widget,))

    @misc.create_task
    async def global_action_cb(self, action, parameter, widget):
        if not widget.left_selected_item:
            return
        path = widget.left_selected_item.joined_path
        window = widget.get_root()
        if action.get_name() == 'save':
            if not widget.edit_stack.transactions:
                return
            if await self.save_playlist(window, path, [item.get_key() for item in widget.main.item_model]):
                widget.edit_stack.reset()
                widget.edit_stack_changed()
        elif action.get_name() == 'rename':
            await self.rename_playlist(window, path, widget.left_selected_item.kind == NODE_FOLDER)
        elif action.get_name() == 'delete':
            await self.delete_playlist(window, path)
        elif action.get_name() == 'update-from-queue':
            await self.save_playlist(window, path, await self.ampd.playlist())

    async def save_playlist(self, window, playlist_path, filenames):
        playlist_name = playlist_path.replace('/', self.PSEUDO_SEPARATOR)

        if playlist_name in self.playlists and not await dialog.MessageDialogAsync(transient_for=window, message=_("Replace existing playlist {name}?").format(name=playlist_path)).run():
            return False

        try:
            await self.ampd.rm(self.TEMPNAME)
        except ampd.ReplyError:
            pass
        try:
            await self.ampd.command_list([self.ampd.playlistadd(self.TEMPNAME, name) for name in filenames])
            if playlist_name in self.playlists:
                await self.ampd.rm(playlist_name)
            await self.ampd.rename(self.TEMPNAME, playlist_name)
        except Exception:
            try:
                await self.ampd.rm(self.TEMPNAME)
            except ampd.ReplyError:
                pass
            raise
        return True

    async def rename_playlist(self, window, old_path, folder):
        title = _("Rename playlist folder") if folder else _("Rename playlist")
        dialog_ = ChoosePathDialog(transient_for=window, title=title, paths=self.playlist_paths(), init=old_path)
        new_path = await dialog_.run()
        if new_path is None or old_path == new_path:
            return

        old_real = old_path.replace('/', self.PSEUDO_SEPARATOR)
        new_real = new_path.replace('/', self.PSEUDO_SEPARATOR)

        if folder:
            for name in self.playlists:
                if name.startswith(old_real):
                    suffix = name[len(old_real):]
                    await self.ampd.rename(name, new_real + suffix)
        else:
            await self.ampd.rename(old_real, new_real)

    async def delete_playlist(self, window, path):
        if not await dialog.MessageDialogAsync(transient_for=window, message=_("Delete playlist {name}?").format(name=path)).run():
            return
        await self.ampd.rm(path.replace('/', self.PSEUDO_SEPARATOR))

    @ampd.task
    async def action_playlist_saveas_cb(self, action, parameter, view):
        filenames = view.get_filenames(parameter.unpack())
        if not filenames:
            await dialog.MessageDialogAsync(message=_("Nothing to save!"), transient_for=view.widget.get_root(), title="", cancel_button=False).run()
            return

        playlist_path = await ChoosePathDialog(transient_for=view.get_root(), title=_("Save as playlist"), paths=self.playlist_paths()).run()
        if playlist_path is None:
            return
        await self.save_playlist(view.get_root(), playlist_path, filenames)
