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


from gi.repository import GLib
from gi.repository import Gtk

import ampd

from ..util import record
from ..util import resource
from ..ui import ssde

from . import songlistbase
from . import songlist


class PlayQueue(songlist.SongListTotalsMixin, songlist.SongListAddSpecialMixin, songlistbase.SongListBaseEditableMixin, songlist.SongList):
    editable = True
    duplicate_test_columns = ['Title']

    def __init__(self, unit):
        super().__init__(unit)
        self.current_song_record = None
        self.widget.record_view.add_css_class('playqueue')

        self.actions.add_action(resource.Action('priority', self.action_priority_cb, parameter_type=GLib.VariantType.new('i')))
        self.actions.add_action(resource.Action('shuffle', self.action_shuffle_cb, dangerous=True, protector=unit.unit_persistent))
        self.actions.add_action(resource.Action('go-to-current', self.action_go_to_current_cb))
        self.signal_handler_connect(unit.unit_server.ampd_server_properties, 'notify::current-song', self.notify_current_song_cb)

        for name in self.songlistbase_actions.list_actions():
            if name.startswith('playqueue-ext-'):
                self.songlistbase_actions.remove(name)
        self.cursor_by_profile = {}
        # self.set_cursor = False

        self.view.record_display_hooks.append(self.record_current_song_hook)

    @ampd.task
    async def client_connected_cb(self, client):
        # self.set_cursor = True
        while True:
            self.set_songs(await self.ampd.playlistinfo())
            self.notify_current_song_cb(self.unit.unit_server.ampd_server_properties, None)
            # if self.set_cursor:
            #     self.widget.record_view.set_cursor(self.cursor_by_profile.get(self.unit.unit_server.server_profile) or Gtk.TreePath(), None, False)
            #     self.set_cursor = False
            await self.ampd.idle(ampd.PLAYLIST)

    def record_current_song_hook(self, label, item):
        if self.unit.unit_server.ampd_server_properties.state != 'stop' and item.Id == self.unit.unit_server.ampd_server_properties.current_song.get('Id'):
            label.get_parent().add_css_class('playing')
        if label.name == 'FormattedTime' and item.Prio is not None:
            label.get_parent().add_css_class('high-priority')

    @ampd.task
    async def action_priority_cb(self, action, parameter):
        songs, refs = self.widget.record_view.get_selection_rows()
        if not songs:
            return

        priority = parameter.unpack()
        if priority == -1:
            priority = sum(int(song.get('Prio', 0)) for song in songs) // len(songs)
            struct = ssde.Integer(default=priority, min_value=0, max_value=255)
            priority = await struct.edit_async(self.widget.get_root())
            if priority is None:
                return
        if songs:
            await self.ampd.prioid(priority, *(song['Id'] for song in songs))

    @ampd.task
    async def action_shuffle_cb(self, action, parameter):
        await self.ampd.shuffle()

    def _set_songs(self, songs):  # If not we may lose the cursor and it's hell to get it right.
        n = len(self.view.record_store)
        self.view.record_store.handler_block_by_func(self.mark_duplicates)
        for i, song in enumerate(songs):
            if i < n:
                self.view.record_store[i].set_data(song)
            else:
                self.view.record_store[n:] = map(record.Record, songs[n:])
                break
        else:
            self.view.record_store[len(songs):] = []
        self.view.record_store.handler_unblock_by_func(self.mark_duplicates)
        self.mark_duplicates()

    def action_go_to_current_cb(self, action, parameter):
        Id = self.unit.unit_server.ampd_server_properties.current_song.get('Id')
        if Id is None:
            return
        for position, record_ in enumerate(self.view.record_store_filter):
            if record_.Id == Id:
                self.view.record_view.scroll_to(position, None, Gtk.ListScrollFlags.FOCUS | Gtk.ListScrollFlags.SELECT, None)
                view_height = self.view.record_view_rows.get_allocation().height
                # row_height = self.view.record_view_rows.get_focus_child().get_allocation().height
                self.view.scrolled_record_view.get_vadjustment().set_value(23 * (position + 0.5) - view_height / 2)

    def notify_current_song_cb(self, server_properties, pspec):
        if self.current_song_record is not None:
            self.current_song_record.emit('changed')
        pos = server_properties.current_song.get('Pos')
        if pos is not None:
            self.current_song_record = self.widget.record_store[int(pos)]
            self.current_song_record.emit('changed')
        else:
            self.current_song_record = None

    @ampd.task
    async def remove_records(self, records):
        await self.ampd.command_list(self.ampd.deleteid(record_.Id) for record_ in records)

    @ampd.task
    async def add_records_from_data(self, songs, position):
        await self.ampd.command_list(self.ampd.add(song['file'], position) for song in reversed(songs))

    @ampd.task
    async def view_activate_cb(self, view, position):
        if not self.unit.unit_persistent.protect_active:
            await self.ampd.playid(self.view.record_store_filter[position].Id)
