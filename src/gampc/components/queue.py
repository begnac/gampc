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
from gi.repository import GObject
from gi.repository import Gtk

import ampd

from .. import util
from .. import ui

from . import itemlist
from . import songlist


QUEUE_ID_CSS_PREFIX = 'queue-Id'
QUEUE_PRIORITY_CSS_PREFIX = 'queue-priority'


class QueueItem(util.item.Item):
    Id = GObject.Property()
    Prio = GObject.Property()

    def load(self, value):
        self.Id = value.pop('Id')
        value.pop('Pos')
        self.Prio = value.pop('Prio', None)
        super().load(value)


class QueueItemFactory(ui.view.LabelItemFactory):
    def __init__(self, name):
        super().__init__(name)

        self.binders['Id'] = (self.id_binder,)
        self.binders['Prio'] = (self.prio_binder, name)

    @staticmethod
    def id_binder(widget, item):
        util.misc.add_unique_css_class(widget.get_parent(), QUEUE_ID_CSS_PREFIX, item.Id)

    @staticmethod
    def prio_binder(widget, item, name):
        if name == 'FormattedTime':
            util.misc.add_unique_css_class(widget.get_parent(), QUEUE_PRIORITY_CSS_PREFIX, '' if item.Prio is not None else None)


class Queue(songlist.SongListTotalsMixin, itemlist.ItemListEditableMixin, songlist.SongList):
    editable = True
    duplicate_test_columns = ['Title']

    factory_factory = QueueItemFactory
    item_factory = QueueItem

    def __init__(self, unit):
        super().__init__(unit)
        self.widget.item_view.add_css_class('queue')

        self.actions.add_action(util.resource.Action('priority', self.action_priority_cb, parameter_type=GLib.VariantType.new('i')))
        self.actions.add_action(util.resource.Action('shuffle', self.action_shuffle_cb, dangerous=True, protector=unit.unit_persistent))
        self.actions.add_action(util.resource.Action('go-to-current', self.action_go_to_current_cb))
        self.signal_handler_connect(unit.unit_server.ampd_server_properties, 'notify::current-song', self.notify_current_song_cb)
        self.signal_handler_connect(self.view.item_store_selection, 'selection-changed', self.selection_changed_cb)

        for name in self.itemlist_actions.list_actions():
            if name.startswith('queue-ext-'):
                self.itemlist_actions.remove(name)
        self.cursor_by_profile = {}
        self.set_cursor = False

        self.css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(self.widget.get_display(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def shutdown(self):
        Gtk.StyleContext.remove_provider_for_display(self.widget.get_display(), self.css_provider)
        super().shutdown()

    def _get_widget(self):
        return ui.view.ViewWithCopyPasteSongs(self.fields, self.factory_factory, interface=self.get_item_interface(), separator_file=self.unit.unit_database.SEPARATOR_FILE)

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
        items = self.view.get_selection_items()
        if not items:
            return

        priority = parameter.unpack()
        if priority == -1:
            priority = sum(int(item.Prio or '0') for item in items) // len(items)
            struct = ui.ssde.Integer(default=priority, min_value=0, max_value=255)
            priority = await struct.edit_async(self.widget.get_root())
            if priority is None:
                return

        await self.ampd.prioid(priority, *(item.Id for item in items))

    @ampd.task
    async def action_shuffle_cb(self, action, parameter):
        await self.ampd.shuffle()

    def action_go_to_current_cb(self, action, parameter):
        Id = self.unit.unit_server.ampd_server_properties.current_song.get('Id')
        if Id is None:
            return
        for position, item in enumerate(self.view.item_store_selection):
            if item.Id == Id:
                self.view.item_view.scroll_to(position, None, Gtk.ListScrollFlags.FOCUS | Gtk.ListScrollFlags.SELECT, None)
                view_height = self.view.item_view.rows.get_allocation().height
                # row_height = self.view.item_view.rows.get_focus_child().get_allocation().height
                self.view.scrolled_item_view.get_vadjustment().set_value(23 * (position + 0.5) - view_height / 2)

    def notify_current_song_cb(self, server_properties, pspec):
        Id = server_properties.current_song.get('Id')
        if Id is None:
            PLAYING_CSS = ''
        else:
            PLAYING_CSS = f'''
            columnview.queue > listview > row > cell.{QUEUE_ID_CSS_PREFIX}-{Id} {{
              background: rgba(128,128,128,0.1);
              font-style: italic;
              font-weight: bold;
            }}
            '''
        self.css_provider.load_from_string(PLAYING_CSS)

    @ampd.task
    async def remove_items(self, items):
        await self.ampd.command_list(self.ampd.deleteid(item.Id) for item in items)

    @ampd.task
    async def add_items(self, keys, position):
        await self.ampd.command_list(self.ampd.add(key, position) for key in reversed(keys))

    @ampd.task
    async def view_activate_cb(self, view, position):
        if not self.unit.unit_persistent.protect_active:
            await self.ampd.playid(self.view.item_store_selection[position].Id)
