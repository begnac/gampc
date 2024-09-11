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
# from gi.repository import Gdk
from gi.repository import Gtk

import re
import datetime
# import ast
# import asyncio

import ampd

from ..util import action
from ..util import cleanup
from ..util import db
from ..util import editstack
from ..util import field
from ..util import item
from ..util import misc
from ..util import unit
# from ..util.logger import logger

from ..ui import compound
# from ..ui import contextmenu
from ..ui import dialog

from ..view.actions import ViewWithContextMenu
from ..view.cache import ViewCacheWithCopy, ViewCacheWithEditStack
from ..view.listitem import EditableListItemFactoryBase

from . import mixins
# from . import search


class TandaItem(item.ItemBase):
    tandaid = GObject.Property()
    songs = GObject.Property()
    modified = GObject.Property(type=bool, default=False)

    def load(self, value):
        self.tandaid = value.pop('tandaid')
        self.songs = value.pop('songs')
        super().load(value)


class TandaSongItem(item.Item):
    tandaid = GObject.Property()

    def load(self, value):
        self.tandaid = value.pop('tandaid')
        super().load(value)


class TandaListItemFactory(EditableListItemFactoryBase):
    def __init__(self, name):
        super().__init__(name)
        self.binders.append(('value', self.tanda_binder, name))

    @staticmethod
    def tanda_binder(widget, item_, name):
        EditableListItemFactoryBase.value_binder(widget, item_, name)
        cell = widget.get_parent()
        if 'Last_Played' in name:
            value = item_.get_field('Last_Played_Weeks')
            if value:
                cell.add_css_class(f'last-played-{min(10, int(value))}')
        elif name in ('Rhythm', 'Energy', 'Speed', 'Level'):
            cell.add_css_class(f'property-{item_.get_field(name)}')
        elif name == 'Emotion':
            cell.add_css_class(f'emotion-{item_.get_field(name)}')
        elif name in ('Genre',):
            cell.add_css_class(f'genre-{item_.get_field(name).lower()}')


class TandaEditTandaView(ViewWithContextMenu):
    def __init__(self, *args, separator_file, **kwargs):
        self.separator_file = separator_file
        super().__init__(*args, factory_factory=TandaListItemFactory, selection_model=Gtk.SingleSelection, **kwargs)

    def get_filenames(self, selection):
        if self.item_selection_filter_model:
            return [self.separator_file] + self.item_selection_filter_model[0].songs.items + [self.separator_file]
        else:
            return []


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


class TandaWidget(compound.WidgetWithPaned):
    GENRES = ('Tango', 'Vals', 'Milonga', _("Other"), _("All"))
    GENRE_OTHER = len(GENRES) - 2
    GENRE_ALL = len(GENRES) - 1

    genre_filter = GObject.Property(type=int, default=0)
    current_tandaid = GObject.Property()

    def __init__(self, tandas, queue_model, config, tanda_fields, song_fields, separator_file, cache):
        self.separator_file = separator_file
        self.cache = cache

        self.artist_store = Gtk.StringList()
        self.artist_selection = Gtk.MultiSelection(model=self.artist_store)
        self.artist_selected_model = Gtk.SelectionFilterModel(model=self.artist_selection)
        self.selected_artists = []

        self.tanda_genre_filter = Gtk.CustomFilter.new(self.tanda_genre_filter_func)
        self.tanda_genre_filter_model = Gtk.FilterListModel(filter=self.tanda_genre_filter)

        self.tanda_artist_filter = Gtk.CustomFilter.new(self.tanda_artist_filter_func)
        self.tanda_artist_filter_model = Gtk.FilterListModel(model=self.tanda_genre_filter_model, filter=self.tanda_artist_filter)

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

        self.edit = TandaEdit(self.tanda_artist_filter_model, queue_model, tanda_fields, song_fields, separator_file=separator_file, cache=cache)
        self.view = TandaView(self.tanda_artist_filter_model, song_fields, separator_file=separator_file, cache=cache)
        self.add_cleanup_below(self.edit, self.view)
        self.stack.add_titled(self.edit, 'edit', _("Edit tandas"))
        self.stack.add_titled(self.view, 'view', _("View tandas"))
        self.subwidgets = [self.edit, self.view]
        for widget in self.subwidgets:
            self.bind_property('current-tandaid', widget, 'current-tandaid', GObject.BindingFlags.BIDIRECTIONAL)
        self.subwidget_index = 0

        self.connect_clean(self.tanda_genre_filter_model, 'items-changed', self.tanda_genre_filtered_changed)
        self.connect_clean(self.artist_selected_model, 'items-changed', self.artist_selected_changed)
        self.connect_clean(self, 'notify::genre-filter', lambda *args: self.tanda_genre_filter.changed(Gtk.FilterChange.DIFFERENT))
        self.connect_clean(self.problem_button, 'toggled', lambda *args: self.tanda_genre_filter.changed(Gtk.FilterChange.DIFFERENT))

        self.tanda_genre_filter_model.set_model(tandas)

        misc.remove_control_move_shortcuts_below(self)
        self.add_context_menu_actions(self.generate_actions(), 'tanda', _("Tanda Editor"))

    def cleanup(self):
        super().cleanup()
        self.tanda_genre_filter.set_filter_func(None)
        self.tanda_artist_filter.set_filter_func(None)

    def generate_actions(self):
        yield action.PropertyActionInfo('genre-filter', self, arg_format='i')
        yield action.ActionInfo('switch-subwidget', self.action_subwidget_next_cb, _("Switch tanda view mode"), ['<Control>Tab'])
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
        return tanda.get_field('Artist') in self.selected_artists

    def action_subwidget_next_cb(self, action, param):
        self.subwidget_index = (self.subwidget_index + 1) % len(self.subwidgets)
        self.stack.set_visible_child(self.subwidgets[self.subwidget_index])


class TandaSubWidgetMixin(cleanup.CleanupSignalMixin):
    def __init__(self, *args, separator_file, **kwargs):
        self.separator_file = separator_file
        super().__init__(*args, **kwargs)

    def init_tandaid_view(self, view):
        self.connect_clean(self, 'map', self.map_cb, view)
        self.connect_clean(view.item_selection_filter_model, 'items-changed', self.tandaid_selection_changed_cb)

    @staticmethod
    def map_cb(self, view):
        if self.current_tandaid is None:
            return
        for i, item_ in enumerate(view.item_selection_model):
            if item_.tandaid == self.current_tandaid:
                view.grab_focus()
                GLib.idle_add(view.scroll_to, i)
                return

    def tandaid_selection_changed_cb(self, model, p, r, a):
        self.current_tandaid = model[0].tandaid if model else None


class TandaEdit(TandaSubWidgetMixin, Gtk.Box):
    current_tandaid = GObject.Property()

    def __init__(self, tandas, queue_model, tanda_fields, song_fields, *args, cache, **kwargs):
        super().__init__(*args, **kwargs, orientation=Gtk.Orientation.VERTICAL)

        self.tanda_fields = tanda_fields

        self.tanda_view = TandaEditTandaView(tanda_fields, model=tandas, sortable=True, separator_file=self.separator_file)
        self.song_view = ViewCacheWithEditStack(song_fields, cache=cache, filterable=False, edit_stack_ancestor=1)
        self.song_view.scrolled_item_view.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.song_view.set_vexpand(False)
        self.append(self.tanda_view)
        self.append(self.song_view)
        self.add_cleanup_below(self.tanda_view, self.song_view)

        self.model_to_flatten = Gio.ListStore()
        self.model_to_flatten.append(self.song_view.item_model)
        self.model_to_flatten.append(queue_model)
        self.queue_and_tanda_model = Gtk.FlattenListModel(model=self.model_to_flatten)
        item.setup_find_duplicate_items(self.queue_and_tanda_model, ['Title'], [self.separator_file])

        self.init_tandaid_view(self.tanda_view)
        self.tanda_view.item_view.add_css_class('tanda-edit')

        self.connect_clean(self.tanda_view.item_selection_filter_model, 'items-changed', self.tanda_selection_changed_cb)
        for column in self.tanda_view.item_view.get_columns():
            self.connect_clean(column.get_factory(), 'item-edited', self.tanda_edited_cb)

        self.current_tanda = None

    def tanda_edited_cb(self, factory, pos, name, value):
        assert self.current_tanda == self.tanda_view.item_selection_model[pos]
        GLib.idle_add(self.tanda_edited, name, value)

    def tanda_edited(self, name, value):
        self.current_tanda.songs.append_delta(editstack.DeltaItem(self.current_tanda, name, value or None))

    def tanda_selection_changed_cb(self, model, p, r, a):
        if model:
            self.current_tanda = model[0]
            self.song_view.set_edit_stack(self.current_tanda.songs)
        else:
            self.current_tanda = None
            self.song_view.set_edit_stack(None)

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

    def __init__(self, tandas, *args, **kwargs):
        super().__init__(*args, **kwargs, item_type=TandaSongItem, sortable=False)
        self.connect_clean(tandas, 'items-changed', self.tandas_changed)
        item.setup_find_duplicate_items(self.item_model, ['Title', 'Artist', 'Performer', 'Date'], [self.separator_file])
        self.init_tandaid_view(self)

    def tandas_changed(self, tandas, p, r, a):
        filenames = []
        for tanda in tandas:
            tandaid = tanda.tandaid
            for song in tanda.songs.items:
                filenames.append((song, tandaid))
            filenames.append((self.separator_file, tandaid))
        self.set_keys(filenames)

    async def _splice_keys(self, task, pos, remove, keys):
        real_keys, tandaids = zip(*keys)
        await self.cache.ensure_keys(real_keys)
        if task is not None:
            await task
        self.item_model.splice_values(pos, remove, (dict(self.cache[key], tandaid=tandaid) for key, tandaid in keys))


class TandaDatabase(GObject.Object, db.Database):
    __gsignals__ = {
        'verify-progress': (GObject.SIGNAL_RUN_LAST, None, (float,)),
        'missing-song': (GObject.SIGNAL_RUN_LAST, None, (str, str, str, str, str)),
    }

    MISSING_SONG_FIELDS = 'Artist', 'Title', 'Date', 'Performer'

    def __init__(self, tanda_model, tanda_fields, song_fields, name, cache):
        self.tanda_model = tanda_model
        self.tanda_fields = tanda_fields
        self.song_fields = song_fields
        self.cache = cache

        self.tanda_field_names = ','.join(map(lambda name: f'tandas.{name}', self.tanda_fields.basic_names))
        self.song_field_names = ','.join(map(lambda name: f'songs.{name}', self.song_fields.basic_names))

        db.Database.__init__(self, name)
        super().__init__()

        self.load()

    def setup_database(self, suffix=''):
        self.setup_table(f'tandas{suffix}', 'tandaid INTEGER PRIMARY KEY', self.tanda_fields.basic_names)
        self.setup_table(f'songs{suffix}', 'file TEXT NOT NULL PRIMARY KEY', self.song_fields.basic_names)
        self.connection.cursor().execute(f'CREATE TABLE IF NOT EXISTS tanda_songs{suffix}(tandaid INTEGER NOT NULL, position INTEGER NOT NULL, file TEXT NOT NULL, PRIMARY KEY(tandaid, position), FOREIGN KEY(tandaid) REFERENCES tandas{suffix}, FOREIGN KEY(file) REFERENCES songs{suffix})')

    def clean_database(self):  #  XXXXXXX?????
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

    def load(self):
        query = self.connection.cursor().execute('SELECT tandaid,{} FROM tandas'.format(','.join(self.tanda_fields.basic_names)))
        self.tanda_model.set_values(map(self._tanda_from_record, query))

    # Song stuff

    def song_is_missing(self, key):
        return bool(self.connection.cursor().execute('SELECT ? NOT IN (SELECT file FROM songs)', (key,)).fetchone()[0])

    def get_song(self, key):
        t = self.connection.cursor().execute(f'SELECT {self.song_field_names} FROM songs WHERE file=?', (key,)).fetchone()
        if t is None:
            return {'file': key}
        else:
            return self._song_from_record(t)

    def add_song(self, song):
        if self.song_is_missing(song['file']):
            with self.connection as cursor:
                cursor.execute('INSERT INTO songs(file) VALUES(:file)', song)
                self.update_song(song)

    def update_song(self, song):
        values = self._make_value_list(self.song_fields.basic_names, list(song.keys()), exclude='file')
        with self.connection as cursor:
            cursor.execute(f'UPDATE songs SET {values} WHERE file=:file', song)

    def replace_song(self, old_file, new_song):
        with self.connection as cursor:
            self.add_song(new_song)
            cursor.execute('UPDATE tanda_songs SET file=? WHERE file=?', (new_song['file'], old_file))
            cursor.execute('DELETE FROM songs WHERE file=?', (old_file,))

    def _song_from_record(self, t):
        return self._dict_from_record(t, self.song_fields.basic_names)

    # Tanda stuff

    def get_tanda(self, tandaid):
        t = self.connection.cursor().execute(f'SELECT tandaid, {self.tanda_field_names} FROM tandas WHERE tandaid=?', (tandaid,)).fetchone()
        return t and self._tanda_from_record(t)

    def new_tanda(self, songs):
        tanda = self._tanda_from_songs(songs)
        with self.connection as cursor:
            cursor.execute('INSERT INTO tandas DEFAULT VALUES')
            tanda['tandaid'] = self.connection.last_insert_rowid()
            tanda['_songs'] = songs
            self._fill_tanda(tanda)
            self.update_tanda(tanda)
            self.tanda_model.splice_values(0, 0, [tanda])

    def update_tanda(self, tanda):
        with self.connection as cursor:
            tandaid = tanda['tandaid']
            cursor.execute('UPDATE tandas SET {} WHERE tandaid=:tandaid'.format(self._make_value_list(self.tanda_fields.basic_names, list(tanda.keys()), exclude='tandaid')), tanda)
            self.set_tanda_songs(tandaid, tanda['_songs'])

    def delete_tanda(self, tanda):
        found, pos = self.tanda_model.find(tanda)
        assert found
        with self.connection:
            self.connection.cursor().execute('DELETE FROM tanda_songs WHERE tandaid=?; DELETE FROM tandas WHERE tandaid=?', (tanda.tandaid, tanda.tandaid))
        self.tanda_model.remove(pos)

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

    def _tanda_from_record(self, t):
        tanda = self._dict_from_record(t, ['tandaid'] + self.tanda_fields.basic_names)
        query = self.connection.cursor().execute(f'SELECT {self.song_field_names} FROM tanda_songs,songs USING(file) WHERE tanda_songs.tandaid=? ORDER BY tanda_songs.position', (tanda['tandaid'],))
        tanda['_songs'] = list(map(self._song_from_record, query))
        self._fill_tanda(tanda)
        return tanda

    def _fill_tanda(self, tanda):
        self.tanda_fields.set_derived_fields(tanda)
        tanda['songs'] = editstack.EditStack([song['file'] for song in tanda['_songs']])

    @staticmethod
    def _tanda_from_songs(songs):
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

    # Internal

    @staticmethod
    def _make_value_list(names, available_names, exclude=None):
        operations = [f'{name}=:{name}' for name in names if name in available_names and name != exclude] \
            + [f'{name}=NULL' for name in names if name not in available_names and name != exclude]
        return ', '.join(operations)

    # def reread_tanda(self, tanda):
    #     db_tanda = self.get_tanda(tanda['tandaid'])
    #     if db_tanda is None:
    #         return False
    #     for name in list(tanda.keys()):
    #         if name not in db_tanda:
    #             del tanda[name]
    #     tanda.update(db_tanda)
    #     return True

    # @ampd.task
    # async def action_tanda_verify_cb(self, action, param):
    #     await self.ampd.update()
    #     await self.ampd.idle(ampd.UPDATE)
    #     await self.ampd.idle(ampd.UPDATE)
    #     await self.ampd.idle(ampd.IDLE)
    #     unused = []
    #     updated = []
    #     replaced = []
    #     problem = []
    #     done = [0]
    #     with self.connection:
    #         query = self.connection.cursor().execute('SELECT {},file in (SELECT file from tanda_songs) FROM songs'.format(', '.join(self.song_fields.basic_names))).fetchall()
    #         songs = [self._tuple_to_dict(t, self.song_fields.basic_names + ['used']) for t in query]
    #         used_songs = list(filter(lambda song: song['used'], songs))
    #         unused_songs = list(filter(lambda song: not song['used'], songs))

    #         for song in unused_songs:
    #             logger.info(_("Deleting '{file}'").format_map(song))
    #             self.connection.cursor().execute('DELETE FROM songs WHERE file=:file', song)
    #             unused.append(song['file'])

    #         nsongs = len(used_songs)
    #         await asyncio.wait([self.verify_song(song, nsongs, done, updated, replaced, problem) for song in used_songs])
    #         logger.info(_("Tanda database checked: {unused} songs unused, {updated} updated, {replaced} replaced, {problem} problematic").format(unused=len(unused), updated=len(updated), replaced=len(replaced), problem=len(problem)))
    #         self.load()

    # @ampd.task
    # async def verify_song(self, song, total, done, updated, replaced, problem):
    #     real_song = await self.ampd.find('file', song['file'])
    #     if real_song:
    #         changed = [(name, song.get(name), real_song[0].get(name)) for name in self.song_fields.basic_names if song.get(name) != real_song[0].get(name)]
    #         if changed:
    #             self.update_song(real_song[0])
    #             logger.info(_("Updating metadata for '{file}': ").format_map(song) + ", ".join("{0} {1} => {2}".format(*t) for t in changed))
    #             updated.append(song['file'])
    #     else:
    #         maybe_song = await self.ampd.find(*sum(([field, song.get(field, '')] for field in self.MISSING_SONG_TANDA_FIELDS), []))
    #         if len(maybe_song) == 1:
    #             logger.info(_("Replacing song:"))
    #             logger.info("- " + song['file'])
    #             logger.info("+ " + maybe_song[0]['file'])
    #             self.replace_song(song['file'], maybe_song[0])
    #             replaced.append((song['file'], maybe_song[0]))
    #         else:
    #             logger.info(_("Not sure about '{file}'").format_map(song))
    #             self.emit('missing-song', song['file'], *(song.get(field, '') for field in self.MISSING_SONG_TANDA_FIELDS))
    #             problem.append(song)
    #     done[0] += 1
    #     self.emit('verify-progress', done[0] / total)


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
    columnview.tanda-edit > listview > row > cell.property-{p + 1} {{
      background: rgba({p * 255 // 4},{255 // 2},{255 - p * 255 // 4},1);
    }}
    '''


class __unit__(cleanup.CleanupCssMixin, mixins.UnitComponentQueueActionMixin, mixins.UnitConfigMixin, unit.Unit):
    tandas = GObject.Property()

    TITLE = _("Tandas")
    KEY = '6'

    def __init__(self, manager):
        super().__init__(manager)
        self.config.pane_separator._get(default=100)

        self.css_provider.load_from_string(CSS)
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

        self.tanda_model = item.ItemListStore(TandaItem)
        self.tanda_sorter = Gtk.CustomSorter.new(self.tanda_sort_func)
        self.tanda_sort_model = Gtk.SortListModel(model=self.tanda_model, sorter=self.tanda_sorter)
        self.queue_model = item.ItemListStore()

        self.db = TandaDatabase(self.tanda_model, self.fields, self.unit_fields.fields, self.name, self.unit_database.cache)
        self.update_cache_full(None)

        self.connect_clean(self.unit_database, 'cleared', self.update_cache_full)
        self.connect_clean(self.tanda_model, 'items-changed', self.update_cache_partial)


    #     self.actions.add_action(resource.Action('reset', self.action_tanda_reset_cb))
    #     self.actions.add_action(resource.Action('reset-field', self.action_tanda_field_cb))
    #     self.actions.add_action(resource.Action('fill-field', self.action_tanda_field_cb))

        # self.add_resources(
        #     'app.menu',
        #     # resource.MenuAction('edit/component', 'tanda-edit.fill-field', _("Fill tanda field"), ['<Control>z']),
        #     # resource.MenuAction('edit/component', 'tanda-edit.reset-field', _("Reset tanda field"), ['<Control><Shift>z']),
        #     resource.MenuAction('edit/component', 'tanda-edit.reset', _("Reset tanda"), ['<Control><Shift>r']),
        # )


        # self.setup_menu('tanda-edit', 'context', ['itemlist', 'fields'])
        # self.setup_menu('tanda-edit', 'left-context', ['itemlist', 'fields'])
        # self.setup_menu('tanda-view', 'context', ['itemlist', 'fields'])

    def cleanup(self):
        del self.db
        self.tanda_sort_model.set_model(None)
        self.tanda_sorter.set_sort_func(None)
        super().cleanup()

    def new_widget(self):
        tanda = TandaWidget(self.tanda_sort_model, self.queue_model, self.config.pane_separator, self.fields, self.unit_fields.fields, self.unit_database.SEPARATOR_FILE, cache=self.unit_database.cache)

        tanda.connect_clean(self.unit_persistent, 'notify::protect-requested', lambda unit, pspec: unit.protect_requested and tanda.problem_button.set_active(True))

        tanda.edit.tanda_view.add_context_menu_actions(self.generate_edit_actions(tanda.edit), 'edit', self.TITLE)
        tanda.edit.tanda_view.add_context_menu_actions(self.generate_queue_add_action(tanda.edit.tanda_view, False), 'queue', self.TITLE, protect=self.unit_persistent.protect)
        tanda.connect_clean(tanda.edit.song_view.item_view, 'activate', self.view_activate_cb)

        tanda.view.add_context_menu_actions(self.generate_queue_actions(tanda.view), 'queue', self.TITLE, protect=self.unit_persistent.protect)
        tanda.connect_clean(tanda.view.item_view, 'activate', self.view_activate_cb)

        # self.connect_clean(self.db, 'verify-progress', self.db_verify_progress_cb)
        # self.connect_clean(self.db, 'missing-song', self.db_missing_song_cb)

        return tanda

    def generate_edit_actions(self, edit):
        yield action.ActionInfo('delete', self.action_tanda_delete_cb, _("Delete tanda"), ['<Control>Delete'], activate_args=(edit,))
        yield action.ActionInfo('save', self.action_tanda_save_cb, _("Save tanda"), ['<Control>s'], activate_args=(edit,))

    @misc.create_task
    async def action_tanda_delete_cb(self, action, parameter, edit):
        if edit.current_tanda is None:
            return
        tanda = edit.current_tanda
        name = ' / '.join(filter(lambda x: x, map(tanda.get_field, ('Artist', 'Years', 'Performer'))))
        if await dialog.MessageDialogAsync(transient_for=edit.get_root(), title=_("Delete tanda"), message=_("Delete {tanda}?").format(tanda=name)).run():
            self.db.delete_tanda(tanda)
        # edit.tanda_view.grab_focus()

    def action_tanda_save_cb(self, action, parameter, edit):
        if edit.current_tanda is None:
            return
        tanda = edit.current_tanda
        new_value = dict(tanda.value, _songs=[self.unit_database.cache[filename] for filename in tanda.songs.items])
        self.fields.set_derived_fields(new_value)
        self.db.update_tanda(dict(new_value, tandaid=tanda.tandaid))
        tanda.value = new_value
        tanda.songs.reset()
        edit.song_view.edit_stack_changed()

    # def action_tanda_reset_cb(self, action, parameter):
    #     self.unit.db.reread_tanda(self.current_tanda.get_data())
    #     self.set_songs(self.current_tanda._songs)

    def action_tanda_define_cb(self, action, parameter, view):
        filenames = view.get_filenames(True)
        songs = [self.unit_database.cache[name] for name in filenames]
        self.db.new_tanda(songs)

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

    @ampd.task
    async def client_connected_cb(self, client):
        if self.db.song_is_missing(self.unit_database.SEPARATOR_FILE):
            songs = await self.ampd.find('file', self.unit_database.SEPARATOR_FILE)
            if len(songs) == 1:
                self.unit_database.cache[self.unit_database.SEPARATOR_FILE] = songs[0]
                self.db.add_song(songs[0])
        try:
            while True:
                self.queue_model.set_values(await self.ampd.playlistinfo())
                await self.ampd.idle(ampd.PLAYLIST)
        finally:
            self.queue_model.remove_all()

    def update_cache_full(self, unit):
        if self.unit_database.SEPARATOR_FILE not in self.unit_database.cache:
            self.unit_database.cache[self.unit_database.SEPARATOR_FILE] = self.db.get_song(self.unit_database.SEPARATOR_FILE)
        self.unit_database.update(song for tanda in self.tanda_model for song in tanda.get_field('_songs'))

    def update_cache_partial(self, model, p, r, a):
        self.unit_database.update(song for tanda in self.tanda_model[p:p + a] for song in tanda.get_field('_songs'))

    @staticmethod
    def tanda_key_func(tanda):
        return (
            tanda.get_field('Artist'),
            99 if tanda.get_field('Genre') is None else 1 if 'Tango' in tanda.get_field('Genre') else 2 if 'Vals' in tanda.get_field('Genre') else 3 if 'Milonga' in tanda.get_field('Genre') else 4,
            tanda.get_field('Years', ''),
            tanda.get_field('Performer', ''),
            tanda.get_field('First_Song', ''),
        )

    def tanda_sort_func(self, tanda1, tanda2, data):
        s1 = self.tanda_key_func(tanda1)
        s2 = self.tanda_key_func(tanda2)
        return Gtk.Ordering.LARGER if s1 > s2 else Gtk.Ordering.SMALLER if s1 < s2 else Gtk.Ordering.EQUAL

    @staticmethod
    def get_last_played_weeks(tanda):
        if 'Last_Played' in tanda and tanda['Last_Played']:
            try:
                return (datetime.date.today() - datetime.date(*map(int, tanda['Last_Played'].split('-')))).days // 7
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
