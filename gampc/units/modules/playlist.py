# coding: utf-8
#
# Graphical Asynchronous Music Player Client
#
# Copyright (C) 2015 Itaï BEN YAACOV
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

from gampc.util import ssde
from gampc.util import dialog
from gampc.util import resource
from gampc.util import module
from gampc.units import songlist


class Playlist(songlist.SongListWithEditDelNew, songlist.SongListWithTotals, module.PanedModule):
    title = _("Playlists")
    name = 'playlist'
    key = '5'

    duplicate_test_columns = ['file']

    @property
    def playlist_name(self):
        return self.playlist_names[0] if len(self.playlist_names) == 1 else None

    @playlist_name.setter
    def playlist_name(self, value):
        self.playlist_names = [value]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.actions.add_action(resource.Action('playlist-rename', self.action_playlist_rename_cb))
        self.actions.add_action(resource.Action('playlist-delete', self.action_playlist_delete_cb))
        self.actions.add_action(resource.Action('playlist-update-from-queue', self.action_playlist_update_from_queue_cb))

        self.playlist_names = []
        self.modified = False

        self.left_store = Gtk.ListStore()
        self.left_store.set_column_types([str])
        self.left_treeview.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        self.left_treeview.set_model(self.left_store)
        self.left_treeview.insert_column_with_attributes(0, '', Gtk.CellRendererPixbuf(icon_name='view-list-symbolic'))
        self.left_treeview.insert_column_with_data_func(1, _("Playlist name"), Gtk.CellRendererText(), self.playlist_name_data_func)
        self.left_treeview.connect('row-activated', self.left_treeview_row_activated_cb)

    def playlist_name_data_func(self, column, renderer, store, i):
        name = store.get_value(i, 0)
        if name == self.playlist_name and self.modified:
            renderer.set_property('text', '* ' + name)
            renderer.set_property('font', 'bold italic')
        else:
            renderer.set_property('text', name)
            renderer.set_property('font', None)

    @ampd.task
    async def client_connected_cb(self, client):
        while True:
            playlists = sorted(map(lambda x: x['playlist'], await self.ampd.listplaylists()))
            self.left_store_set_rows(playlists)
            p = Gtk.TreePath.new_from_indices([playlists.index(self.playlist_name)]) if self.playlist_name in playlists else Gtk.TreePath.new_first()
            if (self.left_treeview.get_selection().path_is_selected(p)):
                self.left_treeview_selection_changed_cb()
            else:
                self.left_treeview.set_cursor(p)
            await self.ampd.idle(ampd.STORED_PLAYLIST)

    def action_reset_cb(self, action, parameter):
        super().action_reset_cb(action, parameter)
        self.load_playlist()

    def left_treeview_selection_changed_cb(self, *args):
        store, paths = self.left_treeview.get_selection().get_selected_rows()
        self.playlist_names = [store.get_value(store.get_iter(p), 0) for p in paths]
        self.load_playlist()

    def left_treeview_row_activated_cb(self, left_treeview, p, col):
        self.action_playlist_rename_cb(None, None)

    @ampd.task
    async def load_playlist(self):
        self.set_modified(False)
        self.set_records(sum([(await self.ampd.listplaylistinfo(name)) for name in self.playlist_names], []))
        self.treeview.get_selection().unselect_all()
        self.set_editable(len(self.playlist_names) == 1)

    def set_modified(self, modified=True):
        if modified != self.modified:
            self.modified = modified
            self.left_treeview.queue_draw()
        self.treeview.queue_draw()

    @ampd.task
    async def action_save_cb(self, action, parameter):
        filenames = [song.file for i, p, song in self.store if song._status != self.RECORD_DELETED]
        if await do_save(self, filenames, self.playlist_name, True):
            self.treeview.get_selection().unselect_all()
            self.load_playlist()

    @ampd.task
    async def action_playlist_rename_cb(self, action, parameter):
        struct = ssde.Text(label=_("Rename playlist"), default=self.playlist_name)
        new_name = struct.edit(self.win)
        if new_name and new_name != self.playlist_name:
            await self.ampd.rename(self.playlist_name, new_name)
            self.playlist_name = new_name

    @ampd.task
    async def action_playlist_delete_cb(self, action, parameter):
        if not self.playlist_name:
            return
        dialog_ = dialog.AsyncDialog(parent=self.win, title=_("Delete playlist"))
        dialog_.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
        dialog_.add_button(_("_OK"), Gtk.ResponseType.OK)
        dialog_.get_content_area().add(Gtk.Label(label=_("Delete playlist {name}?").format(name=self.playlist_name), visible=True))
        reply = await dialog_.run_async()
        dialog_.destroy()
        if reply != Gtk.ResponseType.OK:
            return
        await self.ampd.rm(self.playlist_name)

    @ampd.task
    async def action_playlist_update_from_queue_cb(self, action, parameter):
        await do_save(self, await self.ampd.playlist(), self.playlist_name, True)


async def choose_playlist(module_, label, allow_new=True):
    """Choose a playlist."""
    playlists = sorted(map(lambda x: x['playlist'], await module_.ampd.listplaylists()))
    new_playlist = _("<New playlist>")
    if allow_new:
        playlists = [new_playlist] + playlists
    struct = ssde.Choice(playlists, label=label)
    value = await struct.edit_async(module_.win)
    if allow_new and value == new_playlist:
        label = _("New playlist name")
        new_name = "<{}>".format(label)
        struct = ssde.Text(label=label,
                           default=new_name,
                           validator=lambda x: x != new_name)
        value = await struct.edit_async(module_.win)
        new = True
    else:
        new = False
    return value, new


async def do_save(module_, filenames, playlist_name, replace):
    if replace:
        dialog_ = dialog.AsyncDialog(parent=module_.win)
        dialog_.get_content_area().add(Gtk.Label(label=_("Replace existing playlist {}?").format(playlist_name), visible=True))
        dialog_.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
        dialog_.add_button(_("_OK"), Gtk.ResponseType.OK)
        reply = await dialog_.run_async()
        dialog_.destroy()
        if reply != Gtk.ResponseType.OK:
            return False

    tempname = '$$TEMP$$'
    try:
        await module_.ampd.rm(tempname)
    except ampd.ReplyError:
        pass
    try:
        await module_.ampd.command_list([module_.ampd.playlistadd(tempname, name) for name in filenames])
        if replace:
            await module_.ampd.rm(playlist_name)
        await module_.ampd.rename(tempname, playlist_name)
    except Exception:
        try:
            await module_.ampd.rm(tempname)
        except ampd.ReplyError:
            pass
        raise
    return True


@ampd.task
async def action_playlist_add_saveas_cb(songlist_, action, parameter):
    filenames = list(songlist_.get_filenames(parameter.get_boolean()))
    if not filenames:
        dialog_ = dialog.AsyncDialog(parent=songlist_.win, title="")
        dialog_.get_content_area().add(Gtk.Label(label=_("Nothing to save!"), visible=True))
        dialog_.add_button(_("_OK"), Gtk.ResponseType.OK)
        await dialog_.run_async()
        dialog_.destroy()
        return

    saveas = '-saveas' in action.get_name()
    label = _("Save as playlist") if saveas else _("Add to playlist")
    playlist, new = await choose_playlist(songlist_, label)
    if not playlist:
        return
    if saveas:
        await do_save(songlist_, filenames, playlist, not new)
    else:
        await songlist_.ampd.command_list(songlist_.ampd.playlistadd(playlist, filename) for filename in filenames)


class __unit__(songlist.UnitWithPanedSongList):
    MODULE_CLASS = Playlist

    def __init__(self, name, manager):
        super().__init__(name, manager)

        self.new_resource_provider('app.user-action').add_resources(
            resource.UserAction('mod.playlist-saveas(false)', _("Save as playlist"), 'edit/module'),
        )

        self.new_resource_provider('songlist.action').add_resources(
            resource.ActionModel('playlist-add', action_playlist_add_saveas_cb, parameter_type=GLib.VariantType.new('b')),
            resource.ActionModel('playlist-saveas', action_playlist_add_saveas_cb, parameter_type=GLib.VariantType.new('b'))
        )

        self.new_resource_provider('songlist.context.user-action').add_resources(
            resource.UserAction('mod.playlist-add(true)', _("Add to playlist"), 'other'),
        )

        self.new_resource_provider(Playlist.name + '.left-context.user-action').add_resources(
            resource.UserAction('mod.playlist-rename', _("Rename"), 'action'),
            resource.UserAction('mod.playlist-delete', _("Delete"), 'action'),
            resource.UserAction('mod.playlist-update-from-queue', _("Update from play queue"), 'action')
        )
