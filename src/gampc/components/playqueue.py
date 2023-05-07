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


from gi.repository import Gtk

import ampd

from ..util import ssde
from ..util import resource
from . import songlist


class PlayQueue(songlist.SongListWithTotals, songlist.SongListWithAdd):
    duplicate_test_columns = ['Title']

    def __init__(self, unit):
        super().__init__(unit)
        self.actions.add_action(resource.Action('high-priority', self.action_priority_cb))
        self.actions.add_action(resource.Action('normal-priority', self.action_priority_cb))
        self.actions.add_action(resource.Action('choose-priority', self.action_priority_cb))
        self.actions.add_action(resource.Action('shuffle', self.action_shuffle_cb, dangerous=True, protector=unit.unit_persistent))
        self.actions.add_action(resource.Action('go-to-current', self.action_go_to_current_cb))
        self.signal_handler_connect(unit.unit_server.ampd_server_properties, 'notify::current-song', self.notify_current_song_cb)
        for name in self.songlistbase_actions.list_actions():
            if name.startswith('playqueue-ext-'):
                self.songlistbase_actions.remove(name)
        self.treeview.connect('cursor-changed', self.cursor_changed_cb)
        self.cursor_by_profile = {}
        self.set_cursor = False

    def cursor_changed_cb(self, treeview):
        if not self.set_cursor:
            self.cursor_by_profile[self.unit.unit_server.server_profile] = self.treeview.get_cursor().path

    @ampd.task
    async def client_connected_cb(self, client):
        self.set_cursor = True
        while True:
            self.set_records(await self.ampd.playlistinfo())
            if self.set_cursor:
                self.treeview.set_cursor(self.cursor_by_profile.get(self.unit.unit_server.server_profile) or Gtk.TreePath(), None, False)
                self.set_cursor = False
            await self.ampd.idle(ampd.PLAYLIST)

    def data_func(self, column, renderer, store, i, j):
        super().data_func(column, renderer, store, i, j)
        if self.unit.unit_server.ampd_server_properties.state != 'stop' and store.get_record(i).Id == self.unit.unit_server.ampd_server_properties.current_song.get('Id'):
            renderer.set_property('font', 'italic bold')
            bg = self._mix_colors(1, 1, 1)
            renderer.set_property('background-rgba', bg)
        elif column.field.name == 'FormattedTime' and store.get_record(i).Prio is not None:
            bg = self._mix_colors(0, int(store.get_record(i).Prio) / 255.0, 0)
            renderer.set_property('background-rgba', bg)

    @ampd.task
    async def action_priority_cb(self, action, parameter):
        songs, refs = self.treeview.get_selection_rows()
        if not songs:
            return

        if '-choose-' in action.get_name():
            priority = sum(int(song.get('Prio', 0)) for song in songs) // len(songs)
            struct = ssde.Integer(default=priority, min_value=0, max_value=255)
            priority = await struct.edit_async(self.win)
            if priority is None:
                return
        else:
            priority = 255 if '-high-' in action.get_name() else 0
        if songs:
            await self.ampd.prioid(priority, *(song['Id'] for song in songs))

    @ampd.task
    async def action_shuffle_cb(self, action, parameter):
        await self.ampd.shuffle()

    def action_go_to_current_cb(self, action, parameter):
        if self.unit.unit_server.ampd_server_properties.current_song:
            p = Gtk.TreePath.new_from_string(self.unit.unit_server.ampd_server_properties.current_song['Pos'])
            self.treeview.set_cursor(p)
            self.treeview.scroll_to_cell(p, None, True, 0.5, 0.0)

    def notify_current_song_cb(self, *args):
        self.treeview.queue_draw()

    def record_new_cb(self, store, i):
        ampd.task(self.ampd.addid)(store.get_record(i).file, store.get_path(i).get_indices()[0])

    def record_delete_cb(self, store, i):
        song_id = store.get_record(i).Id
        m = int(store.get_string_from_iter(i))
        for n in range(store.iter_n_children()):
            if n != m and store.get_record(store.iter_nth_child(None, n)).Id == song_id:
                ampd.task(self.ampd.command_list)((self.ampd.swap(n, m), self.ampd.delete(m)))
                store.remove(i)
                return
        if not (self.unit.unit_persistent.protect_active and self.unit.unit_server.ampd_server_properties.current_song.get('pos') == song_id):
            ampd.task(self.ampd.deleteid)(song_id)
            store.remove(i)

    @ampd.task
    async def treeview_row_activated_cb(self, treeview, p, column):
        if not self.unit.unit_persistent.protect_active:
            await self.ampd.playid(self.store.get_record(self.store.get_iter(p)).Id)
