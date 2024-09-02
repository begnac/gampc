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


from gi.repository import GObject
from gi.repository import Gtk

import ampd

from ..util import action
from ..util import item
from ..util import misc
from ..util import unit

from ..ui import ssde

from ..view.base import LabelItemFactory
from ..view.cache import ViewWithCopyPasteSong

from ..components import component

from . import mixins


QUEUE_ID_CSS_PREFIX = 'queue-Id'
QUEUE_PRIORITY_CSS_PREFIX = 'queue-priority'


class QueueItem(item.Item):
    Id = GObject.Property()
    Prio = GObject.Property()

    def load(self, value):
        self.Id = value.pop('Id')
        value.pop('Pos')
        self.Prio = value.pop('Prio', None)
        super().load(value)


class QueueItemFactory(LabelItemFactory):
    def __init__(self, name):
        super().__init__(name)

        self.binders['Id'] = (self.id_binder,)
        self.binders['Prio'] = (self.prio_binder, name)

    @staticmethod
    def id_binder(widget, item):
        misc.add_unique_css_class(widget.get_parent(), QUEUE_ID_CSS_PREFIX, item.Id)

    @staticmethod
    def prio_binder(widget, item, name):
        if name == 'FormattedTime':
            misc.add_unique_css_class(widget.get_parent(), QUEUE_PRIORITY_CSS_PREFIX, '' if item.Prio is not None else None)


@component.component_widget
class QueueView(misc.UseAMPDMixin, ViewWithCopyPasteSong):
    current_Id = GObject.Property()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_to_context_menu(self.generate_queue_actions(), 'queue', _("Queue"))
        self.add_to_context_menu(self.generate_priority_actions(), 'priority', _("Priority for random mode"), submenu=True)

    def generate_queue_actions(self):
        yield action.ActionInfo('go-to-current', self.action_go_to_current_cb, _("Go to current song"), ['<Control>z'])

    def generate_priority_actions(self):
        priority = action.ActionInfo('priority', self.action_priority_cb, arg_format='i')
        yield priority
        yield priority.derive(_("High"), arg=255)
        yield priority.derive(_("Normal"), arg=0)
        # yield priority.derive(_("Choose"), arg=-1)

    def action_go_to_current_cb(self, action, parameter):
        if self.current_Id is None:
            return
        for position, item_ in enumerate(self.item_selection_model):
            if item_.Id == self.current_Id:
                self.scroll_to(position)

    @ampd.task
    async def action_priority_cb(self, action, parameter):
        items = self.get_selection_items()
        if not items:
            return

        priority = parameter.unpack()
        if priority == -1:
            priority = sum(int(item.Prio or '0') for item in items) // len(items)
            struct = ssde.Integer(default=priority, min_value=0, max_value=255)
            priority = await struct.edit(self.get_root())
            if priority is None:
                return

        await self.ampd.prioid(priority, *(item_.Id for item_ in items))

    @ampd.task
    async def remove_positions(self, positions):
        await self.ampd.command_list(self.ampd.deleteid(self.item_selection_model[pos].Id) for pos in positions)

    @ampd.task
    async def add_items(self, keys, position):
        await self.ampd.command_list(self.ampd.add(key, position) for key in reversed(keys))

    def set_songs(self, songs, position):
        self.set_values(songs)
        if position is not None:
            self.scroll_to(position)

    def scroll_to(self, position):
        self.item_view.scroll_to(position, None, Gtk.ListScrollFlags.FOCUS | Gtk.ListScrollFlags.SELECT, None)
        view_height = self.item_view.rows.get_allocation().height
        # row_height = self.view.item_view.rows.get_focus_child().get_allocation().height
        self.scrolled_item_view.get_vadjustment().set_value(23 * (position + 0.5) - view_height / 2)


class __unit__(mixins.UnitCssMixin, mixins.UnitServerMixin, unit.Unit):
    queue_songs = GObject.Property()
    current_Id = GObject.Property()

    TITLE = _("Play Queue")
    CSS = f'''
    columnview.queue > listview > row > cell.{QUEUE_PRIORITY_CSS_PREFIX}- {{
      background: rgba(0,255,0,0.5);
    }}
    '''

    def __init__(self, *args):
        super().__init__(*args)
        self.queue_songs = [], None
        self.cursor_by_profile = {}
        self.set_cursor = False
        self.require('database')
        self.require('fields')
        self.require('persistent')
        self.require('component')

        self.unit_component.register_component('queue', self.TITLE, '1', self.new_component)

    def cleanup(self):
        self.unit_component.unregister_component(self.name)
        super().cleanup()

    def new_component(self):
        component = QueueView(fields=self.unit_fields.fields, item_factory=QueueItem, factory_factory=QueueItemFactory, separator_file=self.unit_database.SEPARATOR_FILE, ampd=self.ampd, subtitle=self.TITLE)
        component.add_to_context_menu(self.generate_queue_actions(), 'queue-general', _("General queue operations"), protect=self.unit_persistent.protect)
        component.item_view.add_css_class('queue')
        item.setup_find_duplicate_items(component.item_store, ['Title'], [self.unit_database.SEPARATOR_FILE])

        component.connect_clean(self, 'notify::queue-songs', self.notify_queue_songs_cb, component)
        component.connect_clean(component.item_selection_model, 'selection-changed', self.selection_changed_cb)
        component.connect_clean(self.unit_server.ampd_server_properties, 'notify::current-song', self.notify_current_song_cb)
        component.connect_clean(component.item_view, 'activate', self.view_activate_cb)
        self.bind_property('current-Id', component, 'current-Id')
        component.set_songs(*self.queue_songs)

        return component

    def generate_queue_actions(self):
        yield action.ActionInfo('shuffle', self.action_shuffle_cb, _("Shuffle"), dangerous=True)

    @ampd.task
    async def action_shuffle_cb(self, action, parameter):
        await self.ampd.shuffle()

    @ampd.task
    async def client_connected_cb(self, client):
        self.set_cursor = True
        try:
            while True:
                songs = await self.ampd.playlistinfo()
                self.unit_database.update(songs)
                if self.set_cursor:
                    position = self.cursor_by_profile.get(self.unit_server.server_profile)
                else:
                    position = None
                self.queue_songs = songs, position
                self.set_cursor = False
                await self.ampd.idle(ampd.PLAYLIST)
        finally:
            self.queue_songs = [], None

    @staticmethod
    def notify_queue_songs_cb(self, pspec, component):
        component.set_songs(*self.queue_songs)

    def selection_changed_cb(self, selection, *args):
        selection = list(misc.get_selection(selection))
        if len(selection) == 1:
            self.cursor_by_profile[self.unit_server.server_profile] = selection[0]

    def notify_current_song_cb(self, server_properties, pspec):
        self.current_Id = server_properties.current_song.get('Id')
        if self.current_Id is None:
            CSS = self.CSS
        else:
            CSS = self.CSS + f'''
            columnview.queue > listview > row > cell.{QUEUE_ID_CSS_PREFIX}-{self.current_Id} {{
              background: rgba(128,128,128,0.1);
              font-style: italic;
              font-weight: bold;
            }}
            '''
        self.css_provider.load_from_string(CSS)

    @ampd.task
    async def view_activate_cb(self, item_view, position):
        if not self.unit_persistent.protect_active:
            await self.ampd.playid(item_view.get_model()[position].Id)
