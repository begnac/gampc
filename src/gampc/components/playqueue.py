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

from ..util import ssde
from ..util import resource

from . import songlist


class PlayQueue(songlist.SongListWithTotals, songlist.SongListWithAdd):
    editable = True
    duplicate_test_columns = ['Title']

    def __init__(self, unit):
        super().__init__(unit)
        self.widget.record_view.add_css_class('playqueue')

        self.actions.add_action(resource.Action('priority', self.action_priority_cb, parameter_type=GLib.VariantType.new('i')))
        self.actions.add_action(resource.Action('shuffle', self.action_shuffle_cb, dangerous=True, protector=unit.unit_persistent))
        self.actions.add_action(resource.Action('go-to-current', self.action_go_to_current_cb))
        self.signal_handler_connect(unit.unit_server.ampd_server_properties, 'notify::current-song', self.notify_current_song_cb)
        for name in self.songlistbase_actions.list_actions():
            if name.startswith('playqueue-ext-'):
                self.songlistbase_actions.remove(name)
        # self.widget.record_view.connect('cursor-changed', self.cursor_changed_cb)
        self.cursor_by_profile = {}
        self.set_cursor = False

        self.view.bind_hooks.append(self.current_song_bind_hook)

    # def cursor_changed_cb(self, view):
    #     if not self.set_cursor:
    #         self.cursor_by_profile[self.unit.unit_server.server_profile] = self.widget.column_view.get_cursor().path

    @ampd.task
    async def TEST(self):
        while True:
            await self.ampd.idle(0, timeout=1)
            if self.view.get_root() is None:
                continue
            a = self.view.get_root().get_focus()
            print(a)
            if a is not None:
                print(a, a.get_css_name(), a.get_parent())
    #         self.widget.column_view.queue_draw()
    #         # for col in self.widget.cols.values():
    #         #     print()
    #         #     print(col.name)
    #         #     for x in col.factory.bound:
    #         #         y = x.get_child().get_parent().get_parent()
    #         #         print(y, y.get_parent(), y.has_focus())

    @ampd.task
    async def client_connected_cb(self, client):
        self.set_cursor = True
        # self.TEST()
        while True:
            # self.view.store.handler_block_by_func(self.records_changed_cb)
            self.set_records(await self.ampd.playlistinfo())
            # self.view.store.handler_unblock_by_func(self.records_changed_cb)
            self.widget.record_view.rebind_columns()
            if self.set_cursor:
                # self.widget.record_view.set_cursor(self.cursor_by_profile.get(self.unit.unit_server.server_profile) or Gtk.TreePath(), None, False)
                self.set_cursor = False
            await self.ampd.idle(ampd.PLAYLIST)

    def current_song_bind_hook(self, label, item, name):
        if self.unit.unit_server.ampd_server_properties.state != 'stop' and item.Id == self.unit.unit_server.ampd_server_properties.current_song.get('Id'):
            label.get_parent().add_css_class('playing')
        if name == 'FormattedTime' and item.Prio is not None:
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
            priority = await struct.edit_async(self.widget.get_toplevel())
            if priority is None:
                return
        if songs:
            await self.ampd.prioid(priority, *(song['Id'] for song in songs))

    @ampd.task
    async def action_shuffle_cb(self, action, parameter):
        await self.ampd.shuffle()

    def action_go_to_current_cb(self, action, parameter):
        Id = self.unit.unit_server.ampd_server_properties.current_song.get('Id')
        if Id is None:
            return
        for position, record in enumerate(self.view.store_filter):
            if record.Id == Id:
                self.view.record_view.scroll_to(position, None, Gtk.ListScrollFlags.FOCUS | Gtk.ListScrollFlags.SELECT, None)
                return
                # view_height = self.view.record_view_rows.get_allocation().height
                # row_height = self.view.record_view_rows.get_allocation().height
                # self.view.scrolled_record_view.get_vadjustment().set_value(how_height * (position + 0.5) - view_height / 2)

    def notify_current_song_cb(self, *args):
        self.widget.record_view.rebind_columns()

    # @ampd.task
    # async def records_changed_cb(self, store, position, removed, added):
    #     return
    #     await self.delete(f'{position}:{position + removed}')
    #     for i in range(position, position + added):
    #         await self.ampd.add(store[i].file, i)

    @ampd.task
    async def remove_records(self, records):
        await self.ampd.command_list(self.ampd.deleteid(record.Id) for record in records)

    @ampd.task
    async def add_records(self, position, filenames):
        await self.ampd.command_list(self.ampd.add(filename, position + i) for i, filename in enumerate(filenames))

    # @ampd.task
    # async def records_added_cb(self, store, position, added):
    #     for i in range(position, position + added):
    #         await self.ampd.addid(store[i].file, i)

    # @ampd.task
    # async def records_removed_cb(self, store, position, removed):
    #     for i in range(position, position + removed):
    #         song_id = store[i].Id
    #         for j in range(len(store)):
    #             if i != j and store[j].Id == song_id:
    #                 ampd.task(self.ampd.command_list)((self.ampd.swap(i, j), self.ampd.delete(j)))
    #                 store.remove(i)
    #                 return
    #         if not (self.unit.unit_persistent.protect_active and self.unit.unit_server.ampd_server_properties.current_song.get('pos') == song_id):
    #             ampd.task(self.ampd.deleteid)(song_id)
    #             store.remove(i)

    @ampd.task
    async def view_activate_cb(self, view, position):
        if not self.unit.unit_persistent.protect_active:
            await self.ampd.playid(self.view.store_filter[position].Id)
