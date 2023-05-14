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


from gi.repository import GLib
from gi.repository import Gtk

import ampd

from ..util import unit
from ..util import dialog
from ..util import resource
from ..components import treelist
from ..components import songlist
from ..components import playlist


class ChoosePathDialog(dialog.AsyncTextDialog):
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


class __unit__(songlist.UnitMixinPanedSongList, unit.Unit):
    title = _("Playlists")
    key = '5'

    COMPONENT_CLASS = playlist.Playlist

    def __init__(self, name, manager):
        super().__init__(name, manager)

        self.add_resources(
            'app.menu',
            resource.MenuAction('edit/component', 'mod.playlist-saveas(false)', _("Save as playlist")),
        )

        self.add_resources(
            'songlist.action',
            resource.ActionModel('playlist-add', self.action_playlist_add_saveas_cb, parameter_type=GLib.VariantType.new('b')),
            resource.ActionModel('playlist-saveas', self.action_playlist_add_saveas_cb, parameter_type=GLib.VariantType.new('b'))
        )

        self.add_resources(
            'songlist.context.menu',
            resource.MenuAction('other', 'songlist.playlist-add(true)', _("Add to playlist")),
        )

        self.add_resources(
            'songlist.left-context.menu',
            resource.MenuAction('other', 'songlist.playlist-add(false)', _("Add to playlist")),
        )

        self.add_resources(
            self.name + '.left-context.menu',
            resource.MenuAction('action', 'playlist.rename', _("Rename")),
            resource.MenuAction('action', 'playlist.delete', _("Delete")),
            resource.MenuAction('action', 'playlist.update-from-queue', _("Update from play queue"))
        )

        self.playlists = []
        self.left_store = treelist.TreeStore(self.fill_node, treelist.Node(kind=playlist.NODE_FOLDER))

    def shutdown(self):
        super().shutdown()
        del self.left_store

    @staticmethod
    def get_pseudo_folder_contents(path, pseudo_names):
        prefix = ''.join(folder + playlist.PSEUDO_SEPARATOR for folder in path)
        folders = []
        names = []

        last_folder = None

        for name in pseudo_names:
            if not name.startswith(prefix):
                continue
            name = name[len(prefix):]
            if playlist.PSEUDO_SEPARATOR in name:
                folder_name = name.split(playlist.PSEUDO_SEPARATOR, 1)[0]
                if folder_name != last_folder:
                    last_folder = folder_name
                    folders.append(folder_name)
            else:
                names.append(name)

        return folders, names

    async def fill_node(self, node):
        if node.kind == playlist.NODE_PLAYLIST:
            return

        folders, playlists = self.get_pseudo_folder_contents(node.path, self.playlists)
        node.sub_nodes = \
            [dict(name=name, icon=playlist.ICONS[playlist.NODE_FOLDER], kind=playlist.NODE_FOLDER) for name in sorted(folders)] + \
            [dict(name=name, icon=playlist.ICONS[playlist.NODE_PLAYLIST], kind=playlist.NODE_PLAYLIST) for name in sorted(playlists)]
        node.update_below = True

    @ampd.task
    async def client_connected_cb(self, client):
        try:
            while True:
                self.playlists = sorted(map(lambda entry: entry['playlist'], await self.ampd.listplaylists()))
                await self.left_store.update()
                await self.ampd.idle(ampd.STORED_PLAYLIST)
        finally:
            self.server_playlists = []

    def playlist_paths(self):
        last_path = []
        for playlist_name in self.playlists:
            playlist_path = playlist_name.split(playlist.PSEUDO_SEPARATOR)
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

    @staticmethod
    async def confirm(win, question):
        return await dialog.AsyncMessageDialog(parent=win, message=question).run_async(destroy=True)

    async def save_playlist(self, playlist_path, filenames, win):
        playlist_name = playlist_path.replace('/', playlist.PSEUDO_SEPARATOR)

        if playlist_name in self.playlists and not await self.confirm(win, _("Replace existing playlist {name}?").format(name=playlist_path)):
            return False

        tempname = '$$TEMP$$'
        try:
            await self.ampd.rm(tempname)
        except ampd.ReplyError:
            pass
        try:
            await self.ampd.command_list([self.ampd.playlistadd(tempname, name) for name in filenames])
            if playlist_name in self.playlists:
                await self.ampd.rm(playlist_name)
            await self.ampd.rename(tempname, playlist_name)
        except Exception:
            try:
                await self.ampd.rm(tempname)
            except ampd.ReplyError:
                pass
            raise
        return True

    async def rename_playlist(self, old_path, win, folder):
        title = _("Rename playlist folder") if folder else _("Rename playlist")
        dialog_ = ChoosePathDialog(parent=win, title=title, paths=self.playlist_paths(), init=old_path)
        new_path = await dialog_.run_async(destroy=True)
        if new_path is None or old_path == new_path:
            return

        old_real = old_path.replace('/', playlist.PSEUDO_SEPARATOR)
        new_real = new_path.replace('/', playlist.PSEUDO_SEPARATOR)

        if folder:
            for name in self.playlists:
                if name.startswith(old_real):
                    suffix = name[len(old_real):]
                    await self.ampd.rename(name, new_real + suffix)
        else:
            await self.ampd.rename(old_real, new_real)

    @ampd.task
    async def action_playlist_add_saveas_cb(self, songlist_, action, parameter):
        filenames = list(songlist_.get_filenames(parameter.get_boolean()))
        if not filenames:
            dialog_ = dialog.AsyncDialog(parent=songlist_.widget.get_toplevel(), title="")
            dialog_.get_content_area().add(Gtk.Label(label=_("Nothing to save!"), visible=True))
            dialog_.add_button(_("_OK"), Gtk.ResponseType.OK)
            await dialog_.run_async()
            dialog_.destroy()
            return

        saveas = '-saveas' in action.get_name()
        title = _("Save as playlist") if saveas else _("Add to playlist")
        dialog_ = ChoosePathDialog(parent=songlist_.widget.get_toplevel(), title=title, paths=self.playlist_paths())
        playlist_path = await dialog_.run_async(destroy=True)
        if playlist_path is None:
            return
        playlist_name = playlist_path.replace('/', playlist.PSEUDO_SEPARATOR)
        if not saveas and playlist_name in self.playlists:
            filenames = await self.ampd.listplaylist(playlist_name) + filenames
        await self.save_playlist(playlist_path, filenames, songlist_.widget.get_toplevel())
