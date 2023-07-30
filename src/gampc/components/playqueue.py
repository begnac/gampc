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
from gi.repository import Pango
from gi.repository import Gtk

import ampd

from ..util import misc
from ..util import ssde
from ..util import resource
from . import songlist


class PlayQueue(songlist.SongListWithTotals, songlist.SongListWithAdd):
    duplicate_test_columns = ['Title']

    def __init__(self, unit):
        super().__init__(unit)
        self.widget.column_view.add_css_class('playqueue')
        print(self.widget.column_view.get_css_classes())
        self.actions.add_action(resource.Action('priority', self.action_priority_cb, parameter_type=GLib.VariantType.new('i')))
        self.actions.add_action(resource.Action('shuffle', self.action_shuffle_cb, dangerous=True, protector=unit.unit_persistent))
        # self.actions.add_action(resource.Action('go-to-current', self.action_go_to_current_cb))
        self.signal_handler_connect(unit.unit_server.ampd_server_properties, 'notify::current-song', self.notify_current_song_cb)
        for name in self.songlistbase_actions.list_actions():
            if name.startswith('playqueue-ext-'):
                self.songlistbase_actions.remove(name)
        # self.widget.column_view.connect('cursor-changed', self.cursor_changed_cb)
        self.cursor_by_profile = {}
        self.set_cursor = False

        self.widget.bind_hooks.append(self.current_song_bind_hook)

    def cursor_changed_cb(self, view):
        if not self.set_cursor:
            self.cursor_by_profile[self.unit.unit_server.server_profile] = self.widget.column_view.get_cursor().path

    @ampd.task
    async def TEST(self):
        while True:
            await self.ampd.idle(0, timeout=1)
            self.widget.column_view.queue_draw()
            # for col in self.widget.cols.values():
            #     print()
            #     print(col.name)
            #     for x in col.factory.bound:
            #         y = x.get_child().get_parent().get_parent()
            #         print(y, y.get_parent(), y.has_focus())

    @ampd.task
    async def client_connected_cb(self, client):
        self.set_cursor = True
        self.TEST()
        while True:
            self.set_records(await self.ampd.playlistinfo())
            self.widget.rebind_columns()
            if self.set_cursor:
                # self.widget.column_view.set_cursor(self.cursor_by_profile.get(self.unit.unit_server.server_profile) or Gtk.TreePath(), None, False)
                self.set_cursor = False
            await self.ampd.idle(ampd.PLAYLIST)

    def current_song_bind_hook(self, label, item, name):
        if self.unit.unit_server.ampd_server_properties.state != 'stop' and item.Id == self.unit.unit_server.ampd_server_properties.current_song.get('Id'):
            label.get_parent().add_css_class('playing')
            print(label.get_parent().get_css_classes(), label.get_parent().get_css_name())
        if name == 'FormattedTime' and item.Prio is not None:
            label.get_parent().add_css_class('high-priority')

    @ampd.task
    async def action_priority_cb(self, action, parameter):
        songs, refs = self.widget.column_view.get_selection_rows()
        if not songs:
            return

        priority = parameter.unpack()
        if priority == -1:
            priority = sum(int(song.get('Prio', 0)) for song in songs) // len(songs)
            struct = ssde.Integer(default=priority, min_value=0, max_value=255)
            priority = await struct.edit_async(self.widget.get_toplevel())
            if priority is None:
                return
        if songs:
            await self.ampd.prioid(priority, *(song['Id'] for song in songs))

    @ampd.task
    async def action_shuffle_cb(self, action, parameter):
        await self.ampd.shuffle()

    # def action_go_to_current_cb(self, action, parameter):
    #     if self.unit.unit_server.ampd_server_properties.current_song:
    #         position = int(self.unit.unit_server.ampd_server_properties.current_song['Pos'])
    #         print(position, self.widget.store_selection)
    #         self.widget.store_selection.select_item(position, True)

    def notify_current_song_cb(self, *args):
        self.widget.rebind_columns()

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
    async def view_activate_cb(self, view, position):
        if not self.unit.unit_persistent.protect_active:
            await self.ampd.playid(self.store[position].Id)
