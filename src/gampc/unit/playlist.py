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


from gi.repository import Gio
from gi.repository import Gtk

import ampd

from ..util import action
from ..util import cache
from ..util import cleanup
from ..util import item
from ..util import misc
from ..util import unit

from ..ui import dialog

from ..view.cache import ViewCacheWithCopyPasteSong

from ..control import lefttree
from ..control import editstack

from . import mixins


PSEUDO_SEPARATOR = ' % '


class PlaylistWidget(editstack.WidgetCacheEditStackMixin, lefttree.WidgetWithPanedTreeList):
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

    def left_selection_changed_cb(self, selection, position, n_items):
        super().left_selection_changed_cb(selection, position, n_items)
        if self.left_selected_item and self.left_selected_item.model is None:
            self.main.set_editable(True)
            self.set_edit_stack(self.left_selected_item.edit_stack)
        else:
            self.main.set_editable(False)
            self.set_edit_stack(None)
            self.main.set_keys(sum(map(lambda node: list(node.edit_stack.items),
                                       filter(lambda node: node.model is None,
                                              map(lambda pos: selection[pos].get_item(),
                                                  self.left_selection_pos))), []))

    @staticmethod
    def left_view_activate_cb(left_view, position):
        row = left_view.get_model()[position]
        node = row.get_item()
        if node.model is None:
            left_view.activate_action('playlist-global.rename')
        else:
            lefttree.WidgetWithPanedTreeList.left_view_activate_cb(left_view, position)


class PlaylistCache(cache.AsyncCache):
    def __init__(self, ampd, playlists):
        super().__init__()
        self.ampd = ampd
        self.playlists = playlists

    async def retrieve(self, name):
        return await self.ampd.listplaylistinfo(name), self.playlists[name]


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


class FolderNode(lefttree.Node):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, model_factory=Gtk.FlattenListModel, icon='folder-symbolic', **kwargs)
        self.model_model = Gio.ListStore()
        self.model_model.splice(0, 0, [Gio.ListStore(), Gio.ListStore()])
        self.model.set_model(self.model_model)


class PlaylistTree(lefttree.Tree):
    def __init__(self, cache, update_song_cache):
        super().__init__()
        self.cache = cache
        self.update_song_cache = update_song_cache

    @staticmethod
    def get_root():
        return FolderNode(expanded=True)

    @misc.create_task
    async def fill_node(self, node):
        if node.model is None:
            playlist, last_modified = await self.cache.get_async(PSEUDO_SEPARATOR.join(node.path))
            self.update_song_cache(playlist)
            node.edit_stack.reset()
            node.edit_stack.splice(0, len(node.edit_stack.items), [song['file'] for song in playlist])
        else:
            folders, playlists = self.get_pseudo_folder_contents(node.path)
            self.merge(node.model_model[0], folders, node.expanded, lambda name: FolderNode(name, node.path))
            self.merge(node.model_model[1], playlists, node.expanded, lambda name: lefttree.Node(name, node.path, model_factory=None, icon='view-list-symbolic', edit_stack=editstack.EditStack()))

    def get_pseudo_folder_contents(self, path):
        prefix = PSEUDO_SEPARATOR.join(path + [''])
        folders = []
        names = []

        last_folder = None

        for name in sorted(self.cache.playlists):
            if not name.startswith(prefix):
                continue
            name = name[len(prefix):]
            if PSEUDO_SEPARATOR in name:
                folder_name = name[:name.find(PSEUDO_SEPARATOR)]
                if folder_name != last_folder:
                    last_folder = folder_name
                    folders.append(folder_name)
            else:
                names.append(name)

        return folders, names


class __unit__(cleanup.CleanupCssMixin, mixins.UnitComponentQueueActionMixin, mixins.UnitComponentTandaActionMixin, mixins.UnitConfigMixin, unit.Unit):
    TITLE = _("Playlist")
    KEY = '5'

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

        self.playlists = {}
        self.playlist_cache = PlaylistCache(self.ampd, self.playlists)
        self.tree = PlaylistTree(self.playlist_cache, self.unit_database.update)

    def new_widget(self):
        playlist = PlaylistWidget(self.unit_fields.fields, self.unit_database.SEPARATOR_FILE, self.unit_database.cache, self.config.pane_separator, self.tree)
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
                self.playlists.clear()
                self.playlists.update((entry['playlist'], entry['Last_Modified']) for entry in await self.ampd.listplaylists() if entry['playlist'] != self.TEMPNAME)
                for name, (files, last_modified) in list(self.playlist_cache.items()):
                    if last_modified != self.playlists.get(name):
                        self.playlist_cache.pop(name)
                self.tree.start()
                await self.ampd.idle(ampd.STORED_PLAYLIST)
        finally:
            self.playlists = {}

    def playlist_paths(self):
        last_path = []
        for playlist_name in sorted(self.playlists):
            playlist_path = playlist_name.split(PSEUDO_SEPARATOR)
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
        path = '/'.join(widget.left_selected_item.path)
        window = widget.get_root()
        if action.get_name() == 'save':
            if not widget.edit_stack.transactions:
                return
            if await self.save_playlist(window, path, [item.get_key() for item in widget.main.item_model]):
                widget.edit_stack.reset()
                widget.edit_stack_changed()
        elif action.get_name() == 'rename':
            await self.rename_playlist(window, path, widget.left_selected_item.model is not None)
        elif action.get_name() == 'delete':
            await self.delete_playlist(window, path)
        elif action.get_name() == 'update-from-queue':
            await self.save_playlist(window, path, await self.ampd.playlist())

    async def save_playlist(self, window, playlist_path, filenames):
        playlist_name = playlist_path.replace('/', PSEUDO_SEPARATOR)

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

        old_real = old_path.replace('/', PSEUDO_SEPARATOR)
        new_real = new_path.replace('/', PSEUDO_SEPARATOR)

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
        await self.ampd.rm(path.replace('/', PSEUDO_SEPARATOR))

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
