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

from .. import util
from .. import ui

from . import itemlist
from . import songlist


class QueueItem(util.item.ItemFromCache):
    def __init__(self, cache, server_properties, **kwargs):
        super().__init__(cache, **kwargs)
        self.server_properties = server_properties

    def _set_bound(self, name):
        super()._set_bound(name)
        parent = self.bound[name].get_parent()
        if self.server_properties.state != 'stop' and self.Id == self.server_properties.current_song.get('Id'):
            parent.add_css_class('playing')
        else:
            parent.remove_css_class('playing')
        if name == 'FormattedTime' and self.Prio is not None:
            parent.add_css_class('high-priority')
        else:
            parent.remove_css_class('high-priority')

    def set_value(self, value):
        self.Id = value['Id']
        self.Prio = value.get('Prio')
        super().set_value(value['file'])


class Queue(songlist.SongListTotalsMixin, songlist.SongListAddSpecialMixin, itemlist.ItemListEditableMixin, songlist.SongList):
    editable = True
    duplicate_test_columns = ['Title']

    def __init__(self, unit):
        super().__init__(unit)
        self.current_song_item = None
        self.widget.item_view.add_css_class('queue')

        self.actions.add_action(util.resource.Action('priority', self.action_priority_cb, parameter_type=GLib.VariantType.new('i')))
        self.actions.add_action(util.resource.Action('shuffle', self.action_shuffle_cb, dangerous=True, protector=unit.unit_persistent))
        self.actions.add_action(util.resource.Action('go-to-current', self.action_go_to_current_cb))
        self.signal_handler_connect(unit.unit_server.ampd_server_properties, 'notify::current-song', self.notify_current_song_cb)
        self.signal_handler_connect(self.view.item_selection, 'selection-changed', self.selection_changed_cb)

        for name in self.itemlist_actions.list_actions():
            if name.startswith('queue-ext-'):
                self.itemlist_actions.remove(name)
        self.cursor_by_profile = {}
        self.set_cursor = False

    def item_factory(self):
        return QueueItem(self.unit.database, self.unit.unit_server.ampd_server_properties)

    @ampd.task
    async def client_connected_cb(self, client):
        self.set_cursor = True
        while True:
            self.set_songs(await self.ampd.playlistinfo())
            self.notify_current_song_cb(self.unit.unit_server.ampd_server_properties, None)
            if self.set_cursor:
                position = self.cursor_by_profile.get(self.unit.unit_server.server_profile)
                if position is not None:
                    self.view.item_view.scroll_to(position, None, Gtk.ListScrollFlags.FOCUS | Gtk.ListScrollFlags.SELECT, None)
                self.set_cursor = False
            await self.ampd.idle(ampd.PLAYLIST)

    def selection_changed_cb(self, selection, *args):
        selection = list(util.misc.get_selection(selection))
        if len(selection) == 1:
            self.cursor_by_profile[self.unit.unit_server.server_profile] = selection[0]

    @ampd.task
    async def action_priority_cb(self, action, parameter):
        songs, refs = self.widget.item_view.get_selection_rows()
        if not songs:
            return

        priority = parameter.unpack()
        if priority == -1:
            priority = sum(int(song.get('Prio', 0)) for song in songs) // len(songs)
            struct = ui.ssde.Integer(default=priority, min_value=0, max_value=255)
            priority = await struct.edit_async(self.widget.get_root())
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
        for position, item_ in enumerate(self.view.item_store_filter):
            if item_.Id == Id:
                self.view.item_view.scroll_to(position, None, Gtk.ListScrollFlags.FOCUS | Gtk.ListScrollFlags.SELECT, None)
                view_height = self.view.item_view_rows.get_allocation().height
                # row_height = self.view.item_view_rows.get_focus_child().get_allocation().height
                self.view.scrolled_item_view.get_vadjustment().set_value(23 * (position + 0.5) - view_height / 2)

    def notify_current_song_cb(self, server_properties, pspec):
        if self.current_song_item is not None:
            self.current_song_item.rebind()
        pos = server_properties.current_song.get('Pos')
        if pos is not None:
            self.current_song_item = self.widget.item_store[int(pos)]
            self.current_song_item.rebind()
        else:
            self.current_song_item = None

    @ampd.task
    async def remove_items(self, items):
        await self.ampd.command_list(self.ampd.deleteid(item.Id) for item in items)

    @ampd.task
    async def add_items(self, strings, position):
        await self.ampd.command_list(self.ampd.add(string, position) for string in reversed(strings))

    @ampd.task
    async def view_activate_cb(self, view, position):
        if not self.unit.unit_persistent.protect_active:
            await self.ampd.playid(self.view.item_store_filter[position].Id)
