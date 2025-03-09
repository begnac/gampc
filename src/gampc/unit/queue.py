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

import ampd

from ..util import action
from ..util import cleanup
from ..util import item
from ..util import misc
from ..util import unit

from ..ui import dialog

from ..view.cache import ViewWithCopyPasteSong

from . import mixins


QUEUE_ID_CSS_PREFIX = 'queue-Id'
QUEUE_PRIORITY_CSS_PREFIX = 'queue-priority'


class QueueSongItem(item.SongItem):
    Id = GObject.Property()
    Prio = GObject.Property()

    def new_value(self, value):
        self.Id = value.pop('Id')
        value.pop('Pos')
        self.Prio = value.pop('Prio', None)
        super().new_value(value)

    def get_binders(self):
        yield from super().get_binders()
        yield 'Id', self.id_binder
        yield 'Prio', self.prio_binder

    def id_binder(self, widget):
        misc.add_unique_css_class(widget.get_parent(), 'Id', self.Id)

    def prio_binder(self, widget):
        if widget.get_name() == 'FormattedTime':
            misc.add_unique_css_class(widget.get_parent(), QUEUE_PRIORITY_CSS_PREFIX, '' if self.Prio is not None else None)


class QueueTransaction:
    def __init__(self, model, ampd):
        self.model = model
        self.ampd = ampd
        self.hold_count = 0

    def add_items(self, position, keys):
        self.lock()
        if self.valid:
            if self.add is None:
                self.add = position, keys
            else:
                self.valid = False
        self.unlock()

    def remove_positions(self, positions):
        self.lock()
        if self.valid:
            for p in positions:
                self.remove.setdefault(self.model[p].get_key(), []).append((p, self.model[p].Id))
        self.unlock()

    def lock(self):
        if self.hold_count == 0:
            self.valid = True
            self.add = None
            self.remove = {}
        self.hold_count += 1

    def unlock(self):
        self.hold_count -= 1
        if self.hold_count == 0:
            if self.valid:
                self.run()
            del self.valid, self.add, self.remove

    def run(self):
        commands = []
        if self.add is not None:
            p, keys = self.add
            p0 = p
            for key in keys:
                if key in self.remove:
                    q, Id = self.remove[key].pop(0)
                    if not self.remove[key]:
                        del self.remove[key]
                    if q < p0:
                        p -= 1
                    commands.append(self.ampd.moveid(Id, p))
                else:
                    commands.append(self.ampd.add(key, p))
                p += 1
        while self.remove:
            key, remove = self.remove.popitem()
            commands += [self.ampd.deleteid(Id) for p, Id in remove]
        self._run(commands)

    @ampd.task
    async def _run(self, commands):
        await self.ampd.command_list(commands)


class QueueWidget(ViewWithCopyPasteSong):
    current_Id = GObject.Property()

    def __init__(self, transaction, **kwargs):
        self.lock = transaction.lock
        self.unlock = transaction.unlock
        self.add_items = transaction.add_items
        self.remove_positions = transaction.remove_positions

        super().__init__(**kwargs)
        self.item_view.add_css_class('queue')
        self.item_view.remove_css_class('song-by-key')
        self.item_view.add_css_class('song-by-Id')
        self.add_context_menu_actions(self.generate_queue_actions(), 'queue', _("Queue"))

    def generate_queue_actions(self):
        yield action.ActionInfo('go-to-current', self.action_go_to_current_cb, _("Go to current song"), ['<Control>z'])

    def action_go_to_current_cb(self, action, parameter):
        if self.current_Id is None:
            return
        for position, item_ in enumerate(self.item_selection_model):
            if item_.Id == self.current_Id:
                self.scroll_to(position)
                return

    def set_position(self, position):
        if position is not None:
            GLib.idle_add(self.scroll_to, position)


class __unit__(cleanup.CleanupCssMixin, mixins.UnitServerMixin, mixins.UnitComponentTotalsMixin, mixins.UnitComponentPlaylistActionMixin, mixins.UnitComponentTandaActionMixin, unit.Unit):
    queue_position = GObject.Property()
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
        self.cursor_by_profile = {}
        self.set_cursor = False
        self.require('database')
        self.require('song')
        self.require('persistent')

        self.connect_clean(self.unit_server.ampd_server_properties, 'notify::current-song', self.notify_current_song_cb)
        self.notify_current_song_cb(self.unit_server.ampd_server_properties, None)

        self.css_provider.load_from_string(self.CSS)

        self.queue_model = item.ItemListStore(item_type=QueueSongItem)
        item.setup_find_duplicate_items(self.queue_model, ['Title'], [self.unit_database.SEPARATOR_FILE])

        self.transaction = QueueTransaction(self.queue_model, self.ampd)

    def new_widget(self):
        queue = QueueWidget(self.transaction, fields=self.unit_song.fields, separator_file=self.unit_database.SEPARATOR_FILE, model=self.queue_model)

        queue.add_context_menu_actions(self.generate_priority_actions(queue), 'priority', _("Priority for random mode"), submenu=True)
        queue.add_context_menu_actions(self.generate_queue_actions(), 'queue-general', _("General queue operations"), protect=self.unit_persistent.protect)
        queue.connect_clean(self, 'notify::queue-position', self.__class__.notify_queue_position_cb, queue)
        queue.connect_clean(queue.item_selection_model, 'selection-changed', self.selection_changed_cb)
        queue.connect_clean(queue.item_view, 'activate', self.view_activate_cb)
        self.bind_property('current-Id', queue, 'current-Id', GObject.BindingFlags.SYNC_CREATE)
        queue.set_position(self.queue_position)
        queue.totals_store = queue.item_model

        queue.add_context_menu_actions(self.generate_foreign_playlist_actions(queue), 'foreign-playlist', self.TITLE)
        queue.add_context_menu_actions(self.generate_foreign_tanda_actions(queue), 'foreign-tanda', self.TITLE)

        return queue

    def generate_priority_actions(self, queue):
        priority = action.ActionInfo('priority', self.action_priority_cb, arg_format='i', activate_args=(queue,))
        yield priority
        yield priority.derive(_("High"), arg=255)
        yield priority.derive(_("Normal"), arg=0)
        yield priority.derive(_("Choose"), arg=-1)

    @ampd.task
    async def action_priority_cb(self, action, parameter, queue):
        items = list(queue.item_selection_filter_model)
        if not items:
            return

        priority = parameter.unpack()
        if priority == -1:
            priority = sum(int(item_.Prio or '0') for item_ in items) // len(items)
            priority = await dialog.SpinButtonDialogAsync(transient_for=queue.get_root(), value=priority, max_value=255).run()
            if priority is None:
                return
            priority = int(priority)

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
                self.queue_model.set_values(songs)
                if self.set_cursor:
                    self.queue_position = self.cursor_by_profile.get(self.unit_server.server_profile)
                    self.set_cursor = False
                else:
                    self.queue_position = None
                await self.ampd.idle(ampd.PLAYLIST)
        finally:
            self.queue_model.remove_all()
            self.queue_position = None

    def notify_queue_position_cb(self, pspec, queue):
        queue.set_position(self.queue_position)

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
    async def add_items(self, position, keys):
        await self.ampd.command_list(self.ampd.add(key, position) for key in reversed(keys))
