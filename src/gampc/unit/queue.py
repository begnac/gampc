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

from ..components import itemlist

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


class QueueView(ViewWithCopyPasteSong):
    def __init__(self, *args, ampd, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_to_context_menu(self.generate_queue_actions(), 'queue', _("Queue"))
        self.add_to_context_menu(self.generate_priority_actions(), 'priority', _("Priority for random mode"), submenu=True)
        self.ampd = ampd
        self.current_Id = None

        self.css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(self.get_display(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def cleanup(self):
        Gtk.StyleContext.remove_provider_for_display(self.get_display(), self.css_provider)
        super().cleanup()

    def set_current_Id(self, Id):
        self.current_Id = Id
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
                self.item_view.scroll_to(position, None, Gtk.ListScrollFlags.FOCUS | Gtk.ListScrollFlags.SELECT, None)
                view_height = self.item_view.rows.get_allocation().height
                # row_height = self.view.item_view.rows.get_focus_child().get_allocation().height
                self.scrolled_item_view.get_vadjustment().set_value(23 * (position + 0.5) - view_height / 2)

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


class Queue(itemlist.SongListTotalsMixin, itemlist.ItemList):
    def __init__(self, unit):
        super().__init__(unit, QueueView(fields=unit.unit_fields.fields, item_factory=QueueItem, factory_factory=QueueItemFactory, separator_file=unit.unit_database.SEPARATOR_FILE, ampd=unit.ampd))
        self.view.add_to_context_menu(self.generate_queue_actions(), 'queue-general', _("General queue operations"), protect=unit.unit_persistent.protect)
        self.view.item_view.add_css_class('queue')
        item.setup_find_duplicate_items(self.view.item_store, ['Title'], [self.unit.unit_database.SEPARATOR_FILE])

        self.widget = self.view

        self.connect_clean(unit.unit_server.ampd_server_properties, 'notify::current-song', self.notify_current_song_cb)
        self.connect_clean(self.view.item_selection_model, 'selection-changed', self.selection_changed_cb)

        # for name in self.itemlist_actions.list_actions():
        #     if name.startswith('queue-ext-'):
        #         self.itemlist_actions.remove(name)
        self.cursor_by_profile = {}
        self.set_cursor = False

    def generate_queue_actions(self):
        yield action.ActionInfo('shuffle', self.action_shuffle_cb, _("Shuffle"), dangerous=True)

    @ampd.task
    async def action_shuffle_cb(self, action, parameter):
        await self.ampd.shuffle()

    @ampd.task
    async def client_connected_cb(self, client):
        self.set_cursor = True
        while True:
            songs = await self.ampd.playlistinfo()
            self.unit.unit_database.update(songs)
            self.view.set_values(songs)
            self.notify_current_song_cb(self.unit.unit_server.ampd_server_properties, None)
            if self.set_cursor:
                position = self.cursor_by_profile.get(self.unit.unit_server.server_profile)
                if position is not None:
                    self.view.item_view.scroll_to(position, None, Gtk.ListScrollFlags.FOCUS | Gtk.ListScrollFlags.SELECT, None)
                self.set_cursor = False
            await self.ampd.idle(ampd.PLAYLIST)

    def selection_changed_cb(self, selection, *args):
        selection = list(misc.get_selection(selection))
        if len(selection) == 1:
            self.cursor_by_profile[self.unit.unit_server.server_profile] = selection[0]

    def notify_current_song_cb(self, server_properties, pspec):
        self.view.set_current_Id(server_properties.current_song.get('Id'))

    @ampd.task
    async def view_activate_cb(self, view, position):
        if not self.unit.unit_persistent.protect_active:
            await self.ampd.playid(self.view.item_selection_model[position].Id)


@ampd.task
async def action_queue_add_replace_cb(songlist_, action, parameter):
    filenames = songlist_.get_filenames(parameter.get_boolean())
    replace = '-replace' in action.get_name()
    if replace:
        await songlist_.ampd.clear()
    await songlist_.ampd.command_list(songlist_.ampd.add(filename) for filename in filenames)
    if replace:
        await songlist_.ampd.play()


@ampd.task
async def action_queue_add_high_priority_cb(songlist_, action, parameter):
    filenames = songlist_.get_filenames(parameter.get_boolean())
    queue = {song['file']: song for song in await songlist_.ampd.playlistinfo()}
    Ids = []
    for filename in filenames:
        Ids.append(queue[filename]['Id'] if filename in queue else await songlist_.ampd.addid(filename))
    await songlist_.ampd.prioid(255, *Ids)


class __unit__(mixins.UnitComponentMixin, mixins.UnitCssMixin, unit.Unit):
    title = _("Play Queue")
    key = '1'

    COMPONENT_CLASS = Queue
    CSS = f'''
    columnview.queue > listview > row > cell.{QUEUE_PRIORITY_CSS_PREFIX}- {{
      background: rgba(0,255,0,0.5);
    }}
    '''

    def __init__(self, *args):
        super().__init__(*args)
        self.require('database')
        self.require('fields')
        self.require('persistent')

        return
        # self.add_resources(
        #     'itemlist.action',
        #     resource.ActionModel('queue-ext-add-high-priority', action_queue_add_high_priority_cb,
        #                          dangerous=True, parameter_type=GLib.VariantType.new('b')),
        #     *(resource.ActionModel('queue-ext' + verb, action_queue_add_replace_cb,
        #                            dangerous=(verb == '-replace'), parameter_type=GLib.VariantType.new('b'))
        #       for verb in ('-add', '-replace')),
        # )

        # for name, parameter in (('context', '(true)'), ('left-context', '(false)')):
        #     self.add_resources(
        #         f'itemlist.{name}.menu',
        #         resource.MenuAction('action', 'itemlist.queue-ext-add' + parameter, _("Add to play queue")),
        #         resource.MenuAction('action', 'itemlist.queue-ext-replace' + parameter, _("Replace play queue")),
        #         resource.MenuAction('action', 'itemlist.queue-ext-add-high-priority' + parameter, _("Add to play queue with high priority")),
        #     )
