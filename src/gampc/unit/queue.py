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

import ampd

from ..util import action
from ..util import cleanup
from ..util import item
from ..util import misc
from ..util import unit

from ..ui import ssde

from ..view.cache import ViewWithCopyPasteSong
from ..view.listitem import LabelListItemFactory

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


class QueueListItemFactory(LabelListItemFactory):
    def __init__(self, name):
        super().__init__(name)

        self.binders['Id'] = (self.id_binder,)
        self.binders['Prio'] = (self.prio_binder, name)

    @staticmethod
    def id_binder(widget, item):
        misc.add_unique_css_class(widget.get_parent(), 'Id', item.Id)

    @staticmethod
    def prio_binder(widget, item, name):
        if name == 'FormattedTime':
            misc.add_unique_css_class(widget.get_parent(), QUEUE_PRIORITY_CSS_PREFIX, '' if item.Prio is not None else None)


class QueueWidget(ViewWithCopyPasteSong):
    current_Id = GObject.Property()

    def __init__(self, add_items, remove_ids, **kwargs):
        self.add_items = add_items
        self.remove_ids = remove_ids
        super().__init__(item_factory=QueueItem, factory_factory=QueueListItemFactory, **kwargs)
        self.item_view.add_css_class('queue')
        self.item_view.remove_css_class('song-by-key')
        self.item_view.add_css_class('song-by-Id')
        item.setup_find_duplicate_items(self.item_model, ['Title'], [self.separator_file])
        self.add_to_context_menu(self.generate_queue_actions(), 'queue', _("Queue"))

    def generate_queue_actions(self):
        yield action.ActionInfo('go-to-current', self.action_go_to_current_cb, _("Go to current song"), ['<Control>z'])

    def action_go_to_current_cb(self, action, parameter):
        if self.current_Id is None:
            return
        for position, item_ in enumerate(self.item_selection_model):
            if item_.Id == self.current_Id:
                self.scroll_to(position)

    @ampd.task
    async def remove_positions(self, positions):
        await self.remove_ids(self.item_selection_model[pos].Id for pos in positions)

    def set_songs(self, songs, position):
        self.set_values(songs)
        if position is not None:
            self.scroll_to(position)


class __unit__(cleanup.CleanupCssMixin, mixins.UnitComponentTotalsMixin, mixins.UnitServerMixin, unit.Unit):
    queue_songs = GObject.Property()
    current_Id = GObject.Property()

    TITLE = _("Play Queue")
    KEY = '1'

    CSS = f'''
    columnview.queue > listview > row > cell.{QUEUE_PRIORITY_CSS_PREFIX}- {{
      background: rgba(0,255,0,0.5);
    }}
    '''

    def __init__(self, manager):
        super().__init__(manager)
        self.queue_songs = [], None
        self.cursor_by_profile = {}
        self.set_cursor = False
        self.require('database')
        self.require('fields')
        self.require('persistent')

        self.connect_clean(self.unit_server.ampd_server_properties, 'notify::current-song', self.notify_current_song_cb)
        self.notify_current_song_cb(self.unit_server.ampd_server_properties, None)

        self.css_provider.load_from_string(self.CSS)

    def new_widget(self):
        queue = QueueWidget(fields=self.unit_fields.fields, separator_file=self.unit_database.SEPARATOR_FILE, add_items=self.add_items, remove_ids=self.remove_ids)

        queue.add_to_context_menu(self.generate_priority_actions(queue), 'priority', _("Priority for random mode"), submenu=True)
        queue.add_to_context_menu(self.generate_queue_actions(), 'queue-general', _("General queue operations"), protect=self.unit_persistent.protect)
        queue.connect_clean(self, 'notify::queue-songs', self.notify_queue_songs_cb, queue)
        queue.connect_clean(queue.item_selection_model, 'selection-changed', self.selection_changed_cb)
        queue.connect_clean(queue.item_view, 'activate', self.view_activate_cb)
        self.bind_property('current-Id', queue, 'current-Id')
        queue.set_songs(*self.queue_songs)
        queue.totals_store = queue.item_model

        return queue

    def generate_priority_actions(self, queue):
        priority = action.ActionInfo('priority', self.action_priority_cb, arg_format='i', activate_args=(queue,))
        yield priority
        yield priority.derive(_("High"), arg=255)
        yield priority.derive(_("Normal"), arg=0)
        # yield priority.derive(_("Choose"), arg=-1)

    @ampd.task
    async def action_priority_cb(self, action, parameter, queue):
        items = list(queue.item_selection_filter_model)
        if not items:
            return

        priority = parameter.unpack()
        if priority == -1:
            priority = sum(int(item.Prio or '0') for item in items) // len(items)
            struct = ssde.Integer(default=priority, min_value=0, max_value=255)
            priority = await struct.edit(queue.get_root())
            if priority is None:
                return

        await self.ampd.prioid(priority, *(item_.Id for item_ in items))

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
    def notify_queue_songs_cb(self, pspec, queue):
        queue.set_songs(*self.queue_songs)

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

    def remove_ids(self, ids):
        return self.ampd.command_list(map(self.ampd.deleteid, ids))

    @ampd.task
    async def add_items(self, keys, position):
        await self.ampd.command_list(self.ampd.add(key, position) for key in reversed(keys))
