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
from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import Gtk

import re
import datetime
import ast
import asyncio

import ampd

from ..util import action
from ..util import cleanup
from ..util import db
from ..util import editstack
from ..util import field
from ..util import item
from ..util import misc
from ..util import unit

from ..ui import compound
from ..ui import contextmenu

from ..view.base import ListItemFactoryBase, EditableListItemFactoryBase
from ..view.actions import ViewWithContextMenu
from ..view.cache import ViewCacheWithCopy, ViewCacheWithEditStack

from . import mixins
from . import search


class StringListItemFactory(Gtk.SignalListItemFactory):
    def __init__(self):
        super().__init__()

        self.connect('setup', self.setup_cb)
        self.connect('bind', self.bind_cb)
        # self.connect('unbind', self.unbind_cb)
        # self.connect('teardown', self.teardown_cb)

    @staticmethod
    def setup_cb(self, listitem):
        listitem.label = Gtk.Label(halign=Gtk.Align.START)
        listitem.set_child(listitem.label)

    @staticmethod
    def bind_cb(self, listitem):
        listitem.label.set_label(listitem.get_item().get_string())

    # @staticmethod
    # def unbind_cb(self, listitem):
    #     pass

    # @staticmethod
    # def teardown_cb(self, listitem):
    #     self.labels.remove(listitem.label)


class TandaItem(item.ItemBase):
    songs = GObject.Property()
    modified = GObject.Property()

    def load(self, value):
        self.songs = value.pop('songs')
        super().load(value)

    def get_key(self):
        return '6666666'


class MyEditableLabel(Gtk.Box):
    def __init__(self, editable=False):
        super().__init__()
        self.editable = editable
        self.label = Gtk.Label()
        self.append(self.label)

    def set_label(self, label):
        self.label.set_label(label)


class MyEditableListItemFactory(ListItemFactoryBase):
    __gsignals__ = {
        'item-edited': (GObject.SIGNAL_RUN_FIRST, None, (int, str, str)),
    }

    def __init__(self, name, always_editable=False):
        super().__init__(name)
        self.always_editable = always_editable

    def make_widget(self):
        return MyEditableLabel()

    # def bind(self, widget, item_):
    #     super().bind(widget, item_)
    #     widget.connect('edited', self.label_edited_cb, self.name)

    # def unbind(self, widget, item_):
    #     super().unbind(widget, item_)
    #     widget.disconnect_by_func(self.label_edited_cb)

    # def label_edited_cb(self, widget, name):
    #     self.emit('item-edited', widget.pos, name, widget.get_text())


class TandaWidget(compound.WidgetWithPaned):
    GENRES = ('Tango', 'Vals', 'Milonga', _("Other"), _("All"))
    GENRE_OTHER = len(GENRES) - 2
    GENRE_ALL = len(GENRES) - 1

    genre_filter = GObject.Property(type=int, default=0)
    current_tandaid = GObject.Property()

    def __init__(self, tandas, config, db, tanda_fields, song_fields, separator_file, cache):
        self.db = db
        self.separator_file = separator_file
        self.cache = cache

        self.artist_store = Gtk.StringList()
        self.artist_selection = Gtk.MultiSelection(model=self.artist_store)
        self.artist_selected_model = Gtk.SelectionFilterModel(model=self.artist_selection)
        self.selected_artists = []

        self.tanda_genre_filter = Gtk.CustomFilter.new(self.tanda_genre_filter_func)
        self.tanda_genre_filter_model = Gtk.FilterListModel(filter=self.tanda_genre_filter)

        self.tanda_sorter = Gtk.CustomSorter.new(self.tanda_sort_func)
        self.tanda_sort_model = Gtk.SortListModel(model=self.tanda_genre_filter_model, sorter=self.tanda_sorter)

        self.tanda_artist_filter = Gtk.CustomFilter.new(self.tanda_artist_filter_func)
        self.tanda_artist_filter_model = Gtk.FilterListModel(model=self.tanda_sort_model, filter=self.tanda_artist_filter)

        self.button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        for i, genre in enumerate(self.GENRES):
            button = Gtk.ToggleButton(label=genre, can_focus=False, action_name='tanda.genre-filter', action_target=GLib.Variant.new_int32(i))
            self.button_box.append(button)
        self.button_box.append(Gtk.Label(hexpand=True))
        self.problem_button = Gtk.ToggleButton(icon_name='object-select-symbolic', can_focus=False, tooltip_text=_("Filter zero note"))
        self.button_box.append(self.problem_button)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.switcher = Gtk.StackSwitcher(stack=self.stack)
        self.button_box.append(self.switcher)

        self.right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        self.right_box.append(self.button_box)
        self.right_box.append(self.stack)

        super().__init__(self.right_box, config, self.artist_selection, StringListItemFactory())

        self.edit = TandaEdit(self.tanda_artist_filter_model, tanda_fields, song_fields, separator_file=separator_file, cache=cache)
        self.view = TandaView(self.tanda_artist_filter_model, song_fields, separator_file=separator_file, cache=cache)
        self.stack.add_titled(self.edit, 'edit', _("Edit tandas"))
        self.stack.add_titled(self.view, 'view', _("View tandas"))
        self.subcomponents = [self.edit, self.view]
        # for c in self.subcomponents:
        #     self.bind_property('current-tandaid', c, 'current-tandaid', GObject.BindingFlags.BIDIRECTIONAL)
        # self.subcomponent_index = 0

        # self.actions_dict['tanda-edit'] = self.edit.actions
        # self.subcomponent_actions_names = 'itemlist', 'fields'
        # for name in self.subcomponent_actions_names:
        #     self.actions_dict[name] = Gio.SimpleActionGroup()
        # self.change_subcomponent_actions(True)

        self.connect_clean(self.tanda_genre_filter_model, 'items-changed', self.tanda_genre_filtered_changed)
        self.connect_clean(self.artist_selected_model, 'items-changed', self.artist_selected_changed)
        self.connect_clean(self, 'notify::genre-filter', lambda *args: self.tanda_genre_filter.changed(Gtk.FilterChange.DIFFERENT))

        # self.connect_clean(self.unit.unit_persistent, 'notify::protect-requested', lambda unit_persistent, param_spec: unit_persistent.protect_requested and self.problem_button.set_active(True))
        # self.connect_clean(self.db, 'changed', self.db_changed_cb)
        # self.connect_clean(self.db, 'verify-progress', self.db_verify_progress_cb)
        # self.connect_clean(self.db, 'missing-song', self.db_missing_song_cb)
        # self.connect_clean(self.problem_button, 'toggled', lambda *args: self.filter_tandas(False))

        self.tanda_genre_filter_model.set_model(tandas)

        self.add_to_context_menu(self.generate_actions(), 'tanda', _("Tanda Editor"))

    def generate_actions(self):
        yield action.PropertyActionInfo('genre-filter', self, arg_format='i')
        # yield action.ActionInfo('switch-subcomponent', self.action_subcomponent_next_cb, _("Switch tanda view mode"), ['<Control>Tab'])
        # yield action.ActionInfo('verify', self.unit.db.action_tanda_verify_cb, _("Verify tanda database"), ['<Control><Shift>d'])
        # yield action.ActionInfo('cleanup-db', self.unit.db.action_cleanup_db_cb, _("Cleanup database"))

    def tanda_genre_filter_func(self, tanda):
        if self.problem_button.get_active() and tanda.get_field('Note') == '0':
            return False
        if self.genre_filter == self.GENRE_ALL:
            return True

        genre = tanda.get_field('Genre', '')

        def test(i):
            return self.GENRES[i] in genre

        return test(self.genre_filter) if self.genre_filter < self.GENRE_OTHER else not any(test(i) for i in range(self.GENRE_OTHER))

    @staticmethod
    def tanda_key_func(tanda):
        return (
            tanda.get_field('Artist'),
            99 if tanda.get_field('Genre') is None else 1 if 'Tango' in tanda.get_field('Genre') else 2 if 'Vals' in tanda.get_field('Genre') else 3 if 'Milonga' in tanda.get_field('Genre') else 4,
            tanda.get_field('Years', ''),
            tanda.get_field('Performer', ''),
            tanda.get_field('First_Song', ''),
        )

    @staticmethod
    def tanda_sort_func(tanda1, tanda2, data):
        s1 = TandaWidget.tanda_key_func(tanda1)
        s2 = TandaWidget.tanda_key_func(tanda2)
        return Gtk.Ordering.LARGER if s1 > s2 else Gtk.Ordering.SMALLER if s1 < s2 else Gtk.Ordering.EQUAL

    def tanda_genre_filtered_changed(self, m, p, r, a):
        artists = sorted(set(tanda.get_field('Artist', '') for tanda in self.tanda_genre_filter_model))
        self.artist_selected_model.handler_block_by_func(self.artist_selected_changed)
        self.artist_selection.unselect_all()
        self.artist_store.splice(0, len(self.artist_store), artists)
        for i, artist in enumerate(artists):
            if artist in self.selected_artists:
                self.artist_selection.select_item(i, False)
        self.artist_selected_model.handler_unblock_by_func(self.artist_selected_changed)

    def artist_selected_changed(self, m, p, r, a):
        self.selected_artists = list(map(lambda item: item.get_string(), self.artist_selected_model))
        self.tanda_artist_filter.changed(Gtk.FilterChange.DIFFERENT)

    def tanda_artist_filter_func(self, tanda):
        return len(self.selected_artists) == 0 or tanda.get_field('Artist') in self.selected_artists








    # def db_changed_cb(self, db, tandaid):
    #     if tandaid == -1:
    #         return self.read_db()

    #     for tanda in self.tandas:
    #         if tanda.get_field('tandaid') == tandaid:
    #             if not self.unit.db.reread_tanda(tanda):
    #                 self.tandas.remove(tanda)
    #             break
    #     else:
    #         tanda = self.unit.db.get_tanda(tandaid)
    #         if tanda:
    #             self.tandas.append(tanda)
    #     self.filter_tandas()

    # def db_verify_progress_cb(self, db, progress):
    #     if progress < 1:
    #         self.status = _("verifying tandas: {progress}%").format(progress=int(progress * 100))
    #     else:
    #         self.status = None

    # def db_missing_song_cb(self, db, song_file, *fields):
    #     search_window = Gtk.Window(destroy_with_parent=True, transient_for=self.widget.get_root(), window_position=Gtk.WindowPosition.CENTER_ON_PARENT,
    #                                default_width=500, default_height=500,
    #                                title=_("Replace {}").format(' / '.join(fields)))
    #     search_window.update_title = lambda *args: None
    #     search_component = search.Search(self.unit)
    #     search_component.entry.set_text(' '.join('{}="{}"'.format(field, fields[i]) for i, field in enumerate(db.MISSING_SONG_FIELDS)))
    #     button_box = Gtk.ButtonBox(layout_style=Gtk.ButtonBoxStyle.CENTER)
    #     cancel_button = Gtk.Button(label=_("_Cancel"), use_underline=True)
    #     cancel_button.connect('clicked', lambda button: button.get_root().destroy())
    #     button_box.add(cancel_button)
    #     ok_button = Gtk.Button(label=_("_OK"), use_underline=True)
    #     ok_button.connect('clicked', self.db_missing_song_ok_cb, db, search_component, song_file)
    #     button_box.add(ok_button)
    #     search_component.widget.add(button_box)
    #     search_window.add(search_component.widget)
    #     search_window.present()

    # @staticmethod
    # def db_missing_song_ok_cb(button, db, search_component, song_file):
    #     path, focus = search_component.view.get_cursor()
    #     if path:
    #         i = search_component.store.get_iter(path)
    #         song = search_component.store.get_record(i).get_data()
    #         db.replace_song(song_file, song)
    #         db.emit('changed', -1)
    #         search_component.widget.get_root().destroy()

# class Tanda(component.Component):
#     def __init__(self, unit):
#         super().__init__(unit)
#         self.widget = TandaWidget(self.config.pane_separator, unit.db, unit.unit_fields.fields, unit.unit_database.SEPARATOR_FILE, cache=unit.unit_database.cache)

#     def cleanup(self):
#         self.change_subcomponent_actions(False)
#         self.edit.cleanup()
#         self.view.cleanup()
#         super().cleanup()

#     @staticmethod
#     def get_left_factory():
#         return StringListItemFactory()

#     def change_subcomponent_actions(self, add):
#         for group_name in self.subcomponent_actions_names:
#             subcomponent_actions = self.subcomponents[self.subcomponent_index].actions_dict[group_name]
#             actions = self.actions_dict[group_name]
#             for name in subcomponent_actions.list_actions():
#                 if add:
#                     actions.add_action(subcomponent_actions.lookup_action(name))
#                 else:
#                     actions.remove_action(name)

#     def action_subcomponent_next_cb(self, action, param):
#         self.change_subcomponent_actions(False)
#         self.subcomponent_index = (self.subcomponent_index + 1) % len(self.subcomponents)
#         self.stack.set_visible_child(self.subcomponents[self.subcomponent_index].widget)
#         self.change_subcomponent_actions(True)


class TandaSubWidgetMixin:
    def __init__(self, *args, separator_file, **kwargs):
        self.separator_file = separator_file
        super().__init__(*args, **kwargs)
        # self.connect('map', self.map_cb)

    # @staticmethod
    # def map_cb(self):
    #     self.set_cursor_tandaid(self.current_tandaid)

    # def init_tandaid_view(self, view):
    #     self.tandaid_view = view
    #     self.connect_clean(self.tandaid_view.record_selection, 'selection-changed', self.tandaid_selection_changed_cb)

    # def set_cursor_tandaid(self, tandaid):
    #     if tandaid is None:
    #         return
    #     for i, item in enumerate(self.tandaid_view.record_selection):
    #         if item._tandaid == tandaid:
    #             self.tandaid_view.record_view.scroll_to(i, None, Gtk.ListScrollFlags.FOCUS | Gtk.ListScrollFlags.SELECT, None)
    #             return

    # def tandaid_selection_changed_cb(self, model, *args):
    #     selection = list(misc.get_selection(model))
    #     self.current_tandaid = model[selection[0]]._tandaid if selection else None


class TandaEdit(TandaSubWidgetMixin, Gtk.Box):
    duplicate_test_columns = ['Title']

    def __init__(self, tandas, tanda_fields, song_fields, *args, cache, **kwargs):
        super().__init__(*args, **kwargs, orientation=Gtk.Orientation.VERTICAL)

        self.tanda_fields = tanda_fields

        self.tanda_view = ViewWithContextMenu(tanda_fields, model=tandas, sortable=True, factory_factory=self.factory_factory)
        self.song_view = ViewCacheWithEditStack(song_fields, cache=cache)
        self.song_view.set_vexpand(False)
        self.append(self.tanda_view)
        self.append(self.song_view)

    def factory_factory(self, name):
        return MyEditableListItemFactory(name)
        return LabelListItemFactory(name)
        return EditableListItemFactoryBase(name)

    #     self.current_tanda = None
    #     self.current_tanda_pos = None

    #     self.actions.add_action(resource.Action('delete', self.action_tanda_delete_cb))
    #     self.actions.add_action(resource.Action('reset', self.action_tanda_reset_cb))
    #     self.actions.add_action(resource.Action('reset-field', self.action_tanda_field_cb))
    #     self.actions.add_action(resource.Action('fill-field', self.action_tanda_field_cb))

    #     self.tanda_view = view.View(self.unit.db.fields, True, unit.unit_misc)
    #     self.tanda_view.record_view.add_css_class('tanda-edit')
    #     self.tanda_view.bind_hooks.append(self.tanda_bind_hook)

    #     # self.tanda_view.connect('button-press-event', self.tanda_view_button_press_event_cb)
    #     self.setup_context_menu(f'{self.name}.left-context', self.tanda_view)
    #     self.init_tandaid_view(self.tanda_view)

    #     # for name in self.unit.db.fields.basic_names:
    #     #     col = self.tanda_view.cols[name]
    #     #     col.renderer.set_property('editable', True)
    #     #     col.renderer.connect('editing-started', self.renderer_editing_started_cb, name)
    #     self.tanda_store = self.tanda_view.record_store
    #     self.signal_handler_connect(self.tanda_view.record_selection, 'selection-changed', self.tanda_selection_changed_cb)

    #     # Ugly hack but works
    #     self.itemlist_actions.remove('filter')
    #     self.itemlist_actions.add_action(Gio.PropertyAction(name='filter', object=self.tanda_view, property_name='filtering'))

    #     self.view.set_vexpand(False)
    #     self.view.scrolled_record_view.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)

    #     self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    #     self.box.append(self.tanda_view)
    #     self.box.append(self.widget)

    #     self.widget = self.box

    # def cleanup(self):
    #     self.tanda_view.cleanup()
    #     super().cleanup()

    # @ampd.task
    # async def client_connected_cb(self, client):
    #     while True:
    #         self.duplicate_extra_records = list(map(record.Record, await self.ampd.playlistinfo()))
    #         self.mark_duplicates()
    #         await self.ampd.idle(ampd.PLAYLIST)

    # def set_tandas(self, tandas):
    #     self.tanda_store[:] = tandas
    #     for tanda in self.tanda_store:
    #         tanda._tandaid = tanda.tandaid
    #     self.current_tanda = None
    #     self.tanda_selection_changed_cb()
    #     # XXXXXXXXXXXXXXXXXXXX CHECK
    #     for record_ in self.tanda_view.record_store:
    #         record_.emit('changed')

    # def tanda_selection_changed_cb(self, *args):
    #     selection = self.tanda_view.get_selection()
    #     self.current_tanda_pos = selection[0] if len(selection) == 1 else None
    #     self.set_current_tanda()

    # def set_current_tanda(self):
    #     if self.current_tanda_pos is None:
    #         self.current_tanda = None
    #         self.set_edit_stack(None)
    #     else:
    #         self.current_tanda = self.tanda_store[self.current_tanda_pos]
    #         self.set_edit_stack(self.current_tanda._edit_stack)
    #     self.edit_stack_changed()

    # def get_filenames(self, selection):
    #     if selection:
    #         return self.view.get_filenames(True)
    #     else:
    #         tanda_selection = self.tanda_view.get_selection()
    #         return sum(([record_.file for record_ in self.tanda_view.record_selection[i]._records] + [self.unit.unit_server.SEPARATOR_FILE] for i in tanda_selection), [self.unit.unit_server.SEPARATOR_FILE])

    # def tanda_bind_hook(self, label, tanda):
    #     if tanda[name] is None:
    #         return
    #     cell = label.get_parent()
    #     if 'Last_Played' in name:
    #         t = min(tanda.Last_Played_Weeks, 10)
    #         cell.add_css_class(f'last-played-{t}')
    #     elif name in ('Rhythm', 'Energy', 'Speed', 'Level'):
    #         cell.add_css_class(f'property-{tanda[name]}')
    #     elif name == 'Emotion':
    #         cell.add_css_class(f'emotion-{tanda[name]}')
    #     elif name in ('Genre',):
    #         cell.add_css_class(f'genre-{tanda[name].lower()}')

    # def edit_stack_changed(self):
    #     super().edit_stack_changed()

    # def set_modified(self, modified=True):
    #     self.current_tanda._modified = modified
    #     self.tanda_view.queue_draw()

    # def renderer_editing_started_cb(self, renderer, editable, path, name):
    #     editable.connect('editing-done', self.editing_done_cb, path, name)
    #     self.unit.unit_misc.block_fragile_accels = True
    #     self.tanda_view.handler_block_by_func(self.tanda_view_button_press_event_cb)

    # def editing_done_cb(self, editable, path, name):
    #     self.tanda_view.handler_unblock_by_func(self.tanda_view_button_press_event_cb)
    #     self.unit.unit_misc.block_fragile_accels = False
    #     if editable.get_property('editing-canceled'):
    #         return
    #     value = editable.get_text() or None
    #     if value != getattr(self.current_tanda, name):
    #         if value:
    #             setattr(self.current_tanda, name, value)
    #         else:
    #             delattr(self.current_tanda, name)
    #         self.set_modified()

    # def tanda_view_button_press_event_cb(self, tanda_view, event):
    #     pos = self.tanda_view.get_path_at_pos(event.x, event.y)
    #     if not pos:
    #         return False
    #     path, col, cx, xy = pos
    #     if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 1:
    #         selection = self.tanda_view.get_selection()
    #         if event.state & Gdk.ModifierType.CONTROL_MASK:
    #             if selection.path_is_selected(path):
    #                 selection.unselect_path(path)
    #             else:
    #                 selection.select_path(path)
    #         elif event.state & Gdk.ModifierType.SHIFT_MASK:
    #             oldpath, column = self.tanda_view.get_cursor()
    #             if oldpath:
    #                 selection.select_range(oldpath, path)
    #             else:
    #                 selection.select_path(path)
    #         else:
    #             self.tanda_view.set_cursor_on_cell(path, col, col.renderer, False)
    #             self.tanda_view.grab_focus()
    #         return True
    #     elif event.type == Gdk.EventType._2BUTTON_PRESS and event.button == 1:
    #         self.tanda_view.set_cursor(path, col, True)
    #         return True

    # def action_tanda_delete_cb(self, action, parameter):
    #     path, column = self.tanda_view.get_cursor()
    #     if not path:
    #         return
    #     i = self.tanda_store.get_iter(path)
    #     tanda = self.tanda_store.get_record(i)
    #     title = ' / '.join(filter(lambda x: x, (tanda.Artist, tanda.Years, tanda.Performer)))
    #     dialog = Gtk.Dialog(parent=self.widget.get_root(), title=_("Delete tanda"))
    #     dialog.get_content_area().add(Gtk.Label(label=_("Delete {tanda}?").format(tanda=title)))
    #     dialog.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
    #     dialog.add_button(_("_OK"), Gtk.ResponseType.OK)
    #     reply = dialog.run()
    #     dialog.destroy()
    #     if reply == Gtk.ResponseType.OK:
    #         self.unit.db.delete_tanda(tanda.tandaid)

    # def action_save_cb(self, action, parameter):
    #     if self.current_tanda:
    #         self.current_tanda._songs = [song.get_data() for i, p, song in self.store]
    #     store, paths = self.tanda_view.get_selection().get_selected_rows()
    #     for path in paths:
    #         tanda = store.get_record(store.get_iter(path))
    #         tanda._songs = [song for song in tanda._songs if song.get('_status') != self.RECORD_DELETED]
    #         self.unit.db.update_tanda(tanda.get_data())

    # def action_reset_cb(self, action, parameter):
    #     self.tanda_genre_filter.filter_.set_data({})
    #     self.tanda_genre_filter.active = False
    #     self.tanda_store.set_sort_column_id(-1, Gtk.SortType.ASCENDING)

    # def action_tanda_reset_cb(self, action, parameter):
    #     self.unit.db.reread_tanda(self.current_tanda.get_data())
    #     self.set_songs(self.current_tanda._songs)

    # def action_tanda_field_cb(self, action, parameter):
    #     path, column = self.tanda_view.get_cursor()
    #     if not path:
    #         return
    #     reset = 'reset' in action.get_name()
    #     tanda = self.tanda_store.get_record(self.tanda_store.get_iter(path))
    #     name = column.field.name
    #     alt_tanda = self.unit.db.get_tanda(tanda.tandaid) if reset else self.unit.db.tanda_from_songs([song for song in tanda._songs if song.get('_status') != self.RECORD_DELETED])
    #     if name in alt_tanda:
    #         setattr(tanda, name, alt_tanda[name])
    #     elif reset:
    #         try:
    #             delattr(tanda, name)
    #         except AttributeError:
    #             pass
    #     if not reset:
    #         self.set_modified()
    #     self.tanda_view.queue_draw()

    # def get_focus(self):
    #     window = self.widget.get_root()
    #     if isinstance(window, Gtk.Window):
    #         return window.get_focus()
    #     return None

    # def action_copy_delete_cb(self, action, parameter):
    #     focus = self.get_focus()
    #     if focus == self.tanda_view and action.get_name() == 'copy':
    #         path, column = focus.get_cursor()
    #         if column:
    #             name = column.field.name
    #             Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(repr({name: self.tanda_store.get_record(self.tanda_store.get_iter(path)).get_data()[name]}), -1)
    #     elif isinstance(focus, Gtk.Entry):
    #         if action.get_name() in ['copy', 'cut']:
    #             focus.emit(action.get_name() + '-clipboard')
    #         else:
    #             focus.emit('delete-from-cursor', Gtk.DeleteType.CHARS, 1)
    #     else:
    #         super().action_copy_delete_cb(action, parameter)

    # def action_paste_cb(self, action, parameter):
    #     focus = self.get_focus()
    #     if isinstance(focus, Gtk.Entry):
    #         focus.emit('paste-clipboard')
    #     else:
    #         super().action_paste_cb(action, parameter)

    # def clipboard_paste_cb(self, clipboard, raw, before):
    #     focus = self.get_focus()
    #     if focus == self.tanda_view:
    #         store, paths = focus.get_selection().get_selected_rows()
    #         to_paste = ast.literal_eval(raw)
    #         if not isinstance(to_paste, dict):
    #             return
    #         for path in paths:
    #             tanda = self.tanda_store.get_record(self.tanda_store.get_iter(path)).get_data()
    #             for name, value in to_paste.items():
    #                 if value:
    #                     tanda[name] = value
    #                 else:
    #                     tanda.pop(name, None)
    #             tanda['_modified'] = True
    #         focus.queue_draw()
    #     else:
    #         self.view.clipboard_paste_cb(clipboard, raw, before)


class TandaView(TandaSubWidgetMixin, ViewCacheWithCopy):
    current_tandaid = GObject.Property()

    duplicate_test_columns = ['Title', 'Artist', 'Performer', 'Date']

    def __init__(self, tandas, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect_clean(tandas, 'items-changed', self.tandas_changed)
        # self.init_tandaid_view(self.view)

    def tandas_changed(self, tandas, p, r, a):
        filenames = [self.separator_file]
        for tanda in tandas:
            # tandaid = tanda['tandaid']
            for song in tanda.songs.items:
                filenames.append(song['file'])
                if song['file'] not in self.cache:
                    self.cache[song['file']] = song
            filenames.append(self.separator_file)
        self.set_keys(filenames)


class TandaDatabase(GObject.Object, db.Database):
    __gsignals__ = {
        'changed': (GObject.SIGNAL_RUN_LAST, None, (int,)),
        'verify-progress': (GObject.SIGNAL_RUN_LAST, None, (float,)),
        'missing-song': (GObject.SIGNAL_RUN_LAST, None, (str, str, str, str, str)),
    }

    MISSING_SONG_FIELDS = 'Artist', 'Title', 'Date', 'Performer'

    def __init__(self, tanda_fields, song_fields, name):
        self.tanda_fields = tanda_fields
        self.tanda_field_names = ','.join(self.tanda_fields.basic_names)
        self.song_fields = song_fields
        self.song_field_names = ','.join(self.song_fields.basic_names)

        db.Database.__init__(self, name)
        super().__init__()
        # self.ampd = unit.ampd.sub_executor()

    def setup_database(self, suffix=''):
        self.setup_table(f'tandas{suffix}', 'tandaid INTEGER PRIMARY KEY', self.tanda_fields.basic_names)
        self.setup_table(f'songs{suffix}', 'file TEXT NOT NULL PRIMARY KEY', self.song_fields.basic_names)
        self.connection.cursor().execute(f'CREATE TABLE IF NOT EXISTS tanda_songs{suffix}(tandaid INTEGER NOT NULL, position INTEGER NOT NULL, file TEXT NOT NULL, PRIMARY KEY(tandaid, position), FOREIGN KEY(tandaid) REFERENCES tandas{suffix}, FOREIGN KEY(file) REFERENCES songs{suffix})')

    def action_cleanup_db_cb(self, action, param):
        with self.connection:
            cursor = self.connection.cursor()
            self.setup_database('_tmp')
            cursor.execute('INSERT INTO songs_tmp({0}) SELECT {0} FROM songs WHERE file IN (SELECT file FROM tanda_songs) ORDER BY file'.format(','.join(self.song_fields.basic_names)))
            for tanda in cursor.execute('SELECT {} FROM tandas ORDER BY Artist'.format(','.join(self.tanda_fields.basic_names + ['tandaid']))).fetchall():
                old_tandaid = tanda[-1]
                tanda = tanda[:-1]
                cursor.execute('INSERT INTO tandas_tmp({}) VALUES({})'.format(','.join(self.tanda_fields.basic_names), ','.join(['?'] * len(tanda))), tanda)
                tandaid = self.connection.last_insert_rowid()
                cursor.execute('INSERT INTO tanda_songs_tmp(tandaid,position,file) SELECT ?,position,file FROM tanda_songs WHERE tandaid=? ORDER BY position', (tandaid, old_tandaid))
            cursor.execute('DROP TABLE tanda_songs')
            cursor.execute('DROP TABLE tandas')
            cursor.execute('DROP TABLE songs')
            cursor.execute('ALTER TABLE tanda_songs_tmp RENAME TO tanda_songs')
            cursor.execute('ALTER TABLE tandas_tmp RENAME TO tandas')
            cursor.execute('ALTER TABLE songs_tmp RENAME TO songs')

    def tuple_to_song(self, t, *extra):
        return self._tuple_to_dict(t, self.song_fields.basic_names + list(extra))

    def song_missing(self, key):
        return bool(self.connection.cursor().execute('SELECT ? NOT IN (SELECT file FROM songs)', (key,)).fetchone()[0])

    def get_song(self, key):
        t = self.connection.cursor().execute(f'SELECT {self.song_field_names} FROM songs WHERE file=?', (key,)).fetchone()
        if t is None:
            return {'file': key}
        else:
            return self.tuple_to_song(t)

    def add_song(self, song):
        if self.song_missing(song['file']):
            with self.connection as cursor:
                cursor.execute('INSERT INTO songs(file) VALUES(:file)', song)
                self.update_song(song)

    def update_song(self, song):
        values = self._make_value_list(self.song_fields.basic_names, list(song.keys()), exclude='file')
        self.connection.cursor().execute(f'UPDATE songs SET {values} WHERE file=:file', song)

    def replace_song(self, old_file, new_song):
        self.add_song(new_song)
        self.connection.cursor().execute('UPDATE tanda_songs SET file=? WHERE file=?', (new_song['file'], old_file))
        self.connection.cursor().execute('DELETE FROM songs WHERE file=?', (old_file,))

    def set_tanda_songs(self, tandaid, songs):
        with self.connection as cursor:
            tanda_songs = dict(cursor.execute('SELECT position, file FROM tanda_songs WHERE tandaid=?', (tandaid,)).fetchall())
            for position, song in enumerate(songs):
                self.add_song(song)
                if position in tanda_songs:
                    if tanda_songs[position] != song['file']:
                        cursor.execute('UPDATE tanda_songs SET file=? WHERE tandaid=? AND position=?', (song['file'], tandaid, position))
                else:
                    cursor.execute('INSERT INTO tanda_songs(tandaid, position, file) VALUES(?, ?, ?)', (tandaid, position, song['file']))
                if position in tanda_songs:
                    del tanda_songs[position]
            cursor.executemany('DELETE FROM tanda_songs WHERE tandaid=? AND position=?', ((tandaid, position) for position in tanda_songs.keys()))

    def get_tandas(self):
        query = self.connection.cursor().execute('SELECT tandaid,{} FROM tandas'.format(','.join(self.tanda_fields.basic_names)))
        return map(self._get_tanda_from_tuple, query)

    def get_tanda(self, tandaid):
        t = self.connection.cursor().execute('SELECT tandaid, {} FROM tandas WHERE tandaid=?'.format(','.join(self.tanda_fields.basic_names)), (tandaid,)).fetchone()
        return t and self._get_tanda_from_tuple(t)

    def reread_tanda(self, tanda):
        db_tanda = self.get_tanda(tanda['tandaid'])
        if db_tanda is None:
            return False
        for name in list(tanda.keys()):
            if name not in db_tanda:
                del tanda[name]
        tanda.update(db_tanda)
        return True

    def _get_tanda_from_tuple(self, t):
        tanda = self._tuple_to_dict(t, ['tandaid'] + self.tanda_fields.basic_names)
        query = self.connection.cursor().execute('SELECT {} FROM tanda_songs,songs USING(file) WHERE tanda_songs.tandaid=?'.format(', songs.'.join(['tanda_songs.position'] + self.song_fields.basic_names)), (tanda['tandaid'],))
        tanda['_songs'] = songs = []
        for s in query:
            song = self._tuple_to_dict(s, ['_position'] + self.song_fields.basic_names)
            self.song_fields.set_derived_fields(song)
            songs.append(song)
        self.tanda_fields.set_derived_fields(tanda)
        tanda['songs'] = editstack.EditStack(songs)
        return tanda

    def update_tanda(self, tanda):
        with self.connection:
            tandaid = tanda['tandaid']
            self.connection.cursor().execute('UPDATE tandas SET {} WHERE tandaid=:tandaid'.format(self._make_value_list(self.tanda_fields.basic_names, list(tanda.keys()), exclude='tandaid')), tanda)
            self.set_tanda_songs(tandaid, tanda['_songs'])
        self.emit('changed', tandaid)

    def delete_tanda(self, tandaid):
        with self.connection:
            self.connection.cursor().execute('DELETE FROM tanda_songs WHERE tandaid=?; DELETE FROM tandas WHERE tandaid=?', (tandaid, tandaid))
        self.emit('changed', tandaid)

    @staticmethod
    def tanda_from_songs(songs):
        tanda_fields = (('ArtistSortName', '???'),
                  ('Genre', '???'),
                  ('PerformersLastNames', '???'))
        merged = {field: [song.get(field, default) for song in songs] for field, default in tanda_fields}
        merged['Genre'] = [genre if genre.split(' ', 1)[0] not in ('Tango', 'Vals', 'Milonga') else genre.split(' ', 1)[0] for genre in merged['Genre']]
        sorted_merged = {field: sorted(set(merged[field])) for field, default in tanda_fields}
        tanda = {}
        tanda['Artist'] = '; '.join(sorted_merged['ArtistSortName'])
        match = re.match(r'(.*) \((.*)\)', tanda['Artist'])
        if match:
            tanda['Artist'] = match.group(1)
            tanda['Comment'] = match.group(2)

        performers = []
        for song_performers in merged['PerformersLastNames']:
            for performer in song_performers.split(', '):
                if performer not in performers:
                    performers.append(performer)
        tanda['Performer'] = ', '.join(performers)
        tanda['Genre'] = ', '.join(sorted_merged['Genre'])
        tanda['Last_Modified'] = str(datetime.date.today())
        return tanda

    @staticmethod
    def _make_value_list(names, available_names, exclude=None):
        operations = [f'{name}=:{name}' for name in names if name in available_names and name != exclude] \
            + [f'{name}=NULL' for name in names if name not in available_names and name != exclude]
        return ', '.join(operations)

    def action_tanda_define_cb(self, songlist, action, parameter):
        songs, rows = songlist.view.get_selection_rows()
        tanda = self.tanda_from_songs(songs)
        with self.connection:
            self.connection.cursor().execute('INSERT INTO tandas DEFAULT VALUES')
            tanda['tandaid'] = tandaid = self.connection.last_insert_rowid()
            self.connection.cursor().execute('UPDATE tandas SET {} WHERE tandaid=:tandaid'.format(self._make_value_list(self.tanda_fields.basic_names, list(tanda.keys()), exclude='tandaid')), tanda)
            self.set_tanda_songs(tandaid, songs)
        self.emit('changed', tandaid)

    @ampd.task
    async def action_tanda_verify_cb(self, action, param):
        await self.ampd.update()
        await self.ampd.idle(ampd.UPDATE)
        await self.ampd.idle(ampd.UPDATE)
        await self.ampd.idle(ampd.IDLE)
        unused = []
        updated = []
        replaced = []
        problem = []
        done = [0]
        with self.connection:
            query = self.connection.cursor().execute('SELECT {},file in (SELECT file from tanda_songs) FROM songs'.format(', '.join(self.song_fields.basic_names))).fetchall()
            songs = [self._tuple_to_dict(t, self.song_fields.basic_names + ['used']) for t in query]
            used_songs = list(filter(lambda song: song['used'], songs))
            unused_songs = list(filter(lambda song: not song['used'], songs))

            for song in unused_songs:
                logger.info(_("Deleting '{file}'").format_map(song))
                self.connection.cursor().execute('DELETE FROM songs WHERE file=:file', song)
                unused.append(song['file'])

            nsongs = len(used_songs)
            await asyncio.wait([self.verify_song(song, nsongs, done, updated, replaced, problem) for song in used_songs])
            logger.info(_("Tanda database checked: {unused} songs unused, {updated} updated, {replaced} replaced, {problem} problematic").format(unused=len(unused), updated=len(updated), replaced=len(replaced), problem=len(problem)))
            self.emit('changed', -1)

    @ampd.task
    async def verify_song(self, song, total, done, updated, replaced, problem):
        real_song = await self.ampd.find('file', song['file'])
        if real_song:
            changed = [(name, song.get(name), real_song[0].get(name)) for name in self.song_fields.basic_names if song.get(name) != real_song[0].get(name)]
            if changed:
                self.update_song(real_song[0])
                logger.info(_("Updating metadata for '{file}': ").format_map(song) + ", ".join("{0} {1} => {2}".format(*t) for t in changed))
                updated.append(song['file'])
        else:
            maybe_song = await self.ampd.find(*sum(([field, song.get(field, '')] for field in self.MISSING_SONG_TANDA_FIELDS), []))
            if len(maybe_song) == 1:
                logger.info(_("Replacing song:"))
                logger.info("- " + song['file'])
                logger.info("+ " + maybe_song[0]['file'])
                self.replace_song(song['file'], maybe_song[0])
                replaced.append((song['file'], maybe_song[0]))
            else:
                logger.info(_("Not sure about '{file}'").format_map(song))
                self.emit('missing-song', song['file'], *(song.get(field, '') for field in self.MISSING_SONG_TANDA_FIELDS))
                problem.append(song)
        done[0] += 1
        self.emit('verify-progress', done[0] / total)


CSS = 'tanda-view.view { outline-width: 4px; outline-style: solid; }'

CSS += '''
columnview.tanda-edit > listview > row > cell.modified {
  font-style: italic;
  font-weight: bold;
}
columnview.tanda-edit > listview > row > cell.emotion-T {
  background: purple;
}
columnview.tanda-edit > listview > row > cell.emotion-R {
  background: pink;
}
columnview.tanda-edit > listview > row > cell.emotion-J {
  background: yellow;
}
columnview.tanda-edit > listview > row > cell.genre-vals {
  background: pink;
}
columnview.tanda-edit > listview > row > cell.genre-milonga {
  background: yellow;
}
'''

for t in range(11):
    CSS += f'''
    columnview.tanda-edit > listview > row > cell.last-played-{t} {{
      background: rgba({255 - t * 255 // 10},{t * 255 // 10},0,1);
    }}
    '''

for p in range(5):
    CSS += f'''
    columnview.tanda-edit > listview > row > cell.property-{p+1} {{
      background: rgba({p * 255 // 4},{255/2},{255 - p * 255 // 4},1);
    }}
    '''


class __unit__(cleanup.CleanupCssMixin, mixins.UnitComponentQueueActionMixin, mixins.UnitConfigMixin, unit.Unit):
    tandas = GObject.Property()

    TITLE = _("Tandas")
    KEY = '6'

    def __init__(self, manager):
        super().__init__(manager)
        self.config.pane_separator._get(default=100)
        self.require('fields')
        self.require('database')
        self.require('persistent')

        self.fields = field.FieldFamily(self.config.fields)
        self.fields.register_field(field.Field('Artist', _("Artist")))
        self.fields.register_field(field.Field('Genre', _("Genre")))
        self.fields.register_field(field.Field('Years_Min', visible=False, get_value=lambda tanda: min(song.get('Date', '').split('-', 1)[0] for song in tanda['_songs']) or '????' if tanda.get('_songs') else None))
        self.fields.register_field(field.Field('Years_Max', visible=False, get_value=lambda tanda: max(song.get('Date', '').split('-', 1)[0] for song in tanda['_songs']) or '????' if tanda.get('_songs') else None))
        self.fields.register_field(field.Field('Years', _("Years"), get_value=lambda tanda: ('\'{}'.format(tanda['Years_Min'][2:]) if tanda['Years_Min'] == tanda['Years_Max'] else '\'{}-\'{}'.format(tanda['Years_Min'][2:], tanda['Years_Max'][2:])) if 'Years_Min' in tanda and 'Years_Max' in tanda else '????'))
        self.fields.register_field(field.Field('First_Song', _("First song"), get_value=lambda tanda: tanda['_songs'][0]['Title'] if '_songs' in tanda else '???'))
        self.fields.register_field(field.Field('Performer', _("Performer")))
        self.fields.register_field(field.Field('Comment', _("Comment")))
        self.fields.register_field(field.Field('Description', _("Description")))
        self.fields.register_field(field.Field('Note', _("Note"), min_width=30))
        self.fields.register_field(field.Field('Rhythm', _("Rhythm"), min_width=30))
        self.fields.register_field(field.Field('Energy', _("Energy"), min_width=30))
        self.fields.register_field(field.Field('Speed', _("Speed"), min_width=30))
        self.fields.register_field(field.Field('Emotion', _("Emotion"), min_width=30))

        # self.fields.register_field(field.Field('Drama', _("Drama"), min_width=30))
        # self.fields.register_field(field.Field('Romance', _("Romance"), min_width=30))
        self.fields.register_field(field.Field('Level', _("Level"), min_width=30))

        self.fields.register_field(field.Field('Last_Modified', _("Last modified")))
        self.fields.register_field(field.Field('Last_Played', _("Last played")))
        self.fields.register_field(field.Field('Last_Played_Weeks', _("Weeks since last played"), min_width=30, get_value=self.get_last_played_weeks))
        self.fields.register_field(field.Field('n_songs', _("Number of songs"), min_width=30, get_value=self.get_n_songs))
        self.fields.register_field(field.Field('Duration', _("Duration"), get_value=lambda tanda: misc.format_time(sum((int(song['Time'])) for song in tanda.get('_songs', [])))))

        self.db = TandaDatabase(self.fields, self.unit_fields.fields, self.name)
        self.tandas = Gio.ListStore()
        self.read_db()

        return
        self.add_resources(
            'app.action',
            resource.ActionModel('tanda-verify', self.db.action_tanda_verify_cb),
            resource.ActionModel('tanda-cleanup-db', self.db.action_cleanup_db_cb),
        )

        self.add_resources(
            'app.menu',
            # resource.MenuAction('edit/component', 'tanda-edit.fill-field', _("Fill tanda field"), ['<Control>z']),
            # resource.MenuAction('edit/component', 'tanda-edit.reset-field', _("Reset tanda field"), ['<Control><Shift>z']),
            resource.MenuAction('edit/component', 'tanda-edit.reset', _("Reset tanda"), ['<Control><Shift>r']),
            resource.MenuAction('edit/component', 'tanda-edit.delete', _("Delete tanda"), ['<Control>Delete']),
        )

        self.add_resources(
            'songlist.action',
            resource.ActionModel('tanda-define', self.db.action_tanda_define_cb),
        )

        self.add_resources(
            'songlist.context.menu',
            resource.MenuAction('other', 'songlist.tanda-define', _("Define tanda")),
        )

        self.add_resources(
            'tanda-edit.left-context.menu',
            resource.MenuAction('edit', 'tanda-edit.delete', _("Delete tanda")),
        )

        self.setup_menu('tanda-edit', 'context', ['itemlist', 'fields'])
        self.setup_menu('tanda-edit', 'left-context', ['itemlist', 'fields'])
        self.setup_menu('tanda-view', 'context', ['itemlist', 'fields'])

    def cleanup(self):
        del self.db
        super().cleanup()

    def new_widget(self):
        tanda = TandaWidget(self.tandas, self.config.pane_separator, self.db, self.fields, self.unit_fields.fields, self.unit_database.SEPARATOR_FILE, cache=self.unit_database.cache)
        return tanda

    def read_db(self):
        if self.unit_database.SEPARATOR_FILE not in self.unit_database.cache:
            self.unit_database.cache[self.unit_database.SEPARATOR_FILE] = self.db.get_song(self.unit_database.SEPARATOR_FILE)
        self.tandas[:] = (TandaItem(value=tanda) for tanda in self.db.get_tandas())

    @ampd.task
    async def client_connected_cb(self, client):
        if self.db.song_missing(self.unit_database.SEPARATOR_FILE):
            songs = await self.ampd.find('file', self.unit_database.SEPARATOR_FILE)
            if len(songs) == 1:
                self.unit_database.cache[self.unit_database.SEPARATOR_FILE] = songs[0]
                self.db.add_song(songs[0])

    @staticmethod
    def get_last_played_weeks(tanda):
        if 'Last_Played' in tanda and tanda['Last_Played']:
            try:
                return str((datetime.date.today() - datetime.date(*map(int, tanda['Last_Played'].split('-')))).days // 7)
            except Exception:
                pass
        return ''

    @staticmethod
    def get_n_songs(tanda):
        n = len(tanda.get('_songs'))
        if (n == 4 and tanda.get('Genre').startswith('Tango')) or (n == 3 and tanda.get('Genre') in {'Vals', 'Milonga'}):
            return ''
        else:
            return str(n)
