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


import asyncio
import datetime
import functools
import re

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import Gtk

import ampd

from ..util import action
from ..util import cleanup
from ..util import config
from ..util import db
from ..util import field
from ..util import item
from ..util import misc
from ..util import unit
from ..util.logger import logger

from ..ui import dialog
from ..ui import editable

from ..view.actions import ViewWithContextMenu
from ..view.cache import ViewCacheWithCopy
from ..view.cache import ViewCacheWithCopyPaste

from ..control import compound
from ..control import editstack

from . import mixins


class TandaItem(item.Item):
    tandaid = GObject.Property()
    songs = GObject.Property()
    edit_stack = GObject.Property()
    modified = GObject.Property(type=bool, default=False)

    def new_value(self, value):
        self.tandaid = value.pop('tandaid')
        self.edit_stack = editstack.EditStack([song['file'] for song in value['_songs']], self)
        self.edit_stack.bind_property('modified', self, 'modified')
        super().new_value(value)

    def get_binders(self):
        yield from super().get_binders()
        yield 'modified', self.modified_binder

    def value_binder(self, widget):
        super().value_binder(widget)
        name = widget.get_name()
        cell = widget.get_parent()
        if 'Last_Played' in name:
            value = self.get_field('Last_Played_Weeks')
            if value is not None:
                value = str(min(10, int(value)))
            misc.add_unique_css_class(cell, 'last-played', value)
        elif name in ('Rhythm', 'Energy', 'Speed', 'Level'):
            misc.add_unique_css_class(cell, 'property', self.get_field(name))
        elif name == 'Emotion':
            misc.add_unique_css_class(cell, 'emotion', self.get_field(name))
        elif name in ('Genre',):
            misc.add_unique_css_class(cell, 'genre', self.get_field(name).lower())

    def modified_binder(self, widget):
        cell = widget.get_parent()
        if self.modified:
            cell.add_css_class('modified')
        else:
            cell.remove_css_class('modified')


class TandaSongItem(item.SongItem):
    tandaid = GObject.Property()

    def new_value(self, value):
        self.tandaid = value.pop('tandaid')
        super().new_value(value)


class TandaEditableLabel(editable.EditableLabel):
    __gsignals__ = {
        'action-fill': (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        trigger = Gtk.KeyvalTrigger(keyval=Gdk.KEY_f, modifiers=Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK)
        self.shortcut.add_shortcut(Gtk.Shortcut(trigger=trigger, action=Gtk.CallbackAction.new(self.__class__.fill_cb)))

    def fill_cb(self, args):
        name = self.get_name()
        alt_tanda = TandaDatabase._tanda_from_songs(self._item.value['_songs'])
        if name in alt_tanda and alt_tanda[name] != self.label.get_label():
            self.edit_manager.emit('edited', self, {name: alt_tanda[name]})


class StringListItemFactory(misc.FactoryBase):
    def setup_cb(self, listitem):
        listitem.set_child(Gtk.Label(halign=Gtk.Align.START))

    def bind_cb(self, listitem):
        listitem.get_child().set_label(listitem.get_item().get_string())


class TandaWidget(compound.WidgetWithPaned):
    GENRES = (_("Tango"), _("Vals"), _("Milonga"), _("Other"), _("All"))
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

        self.button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, can_focus=False)
        for i, genre in enumerate(self.GENRES):
            button = Gtk.ToggleButton(label=genre, can_focus=False, action_name='tanda-widget.genre-filter', action_target=GLib.Variant.new_int32(i))
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

        self.edit = TandaEdit(self.tanda_artist_filter_model, queue_model, tanda_fields, song_fields, separator_file=separator_file, cache=cache, context_menu=self.context_menu)
        self.view = TandaView(self.tanda_artist_filter_model, song_fields, separator_file=separator_file, cache=cache, context_menu=self.context_menu)
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

        self.add_context_menu_actions(self.generate_actions(), 'tanda-widget', _("Tanda Editor"))

    def cleanup(self):
        super().cleanup()
        self.tanda_genre_filter.set_filter_func(None)
        self.tanda_artist_filter.set_filter_func(None)

    def generate_actions(self):
        yield action.PropertyActionInfo('genre-filter', self, arg_format='i')
        yield action.ActionInfo('switch-subwidget', self.action_subwidget_next_cb, _("Switch tanda view mode"), ['<Control>Tab'])

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
        self.connect_clean(self, 'map', self.__class__.map_cb, view)
        self.connect_clean(view.item_selection_filter_model, 'items-changed', self.tandaid_selection_changed_cb)

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


class TandaEditTandaView(ViewWithContextMenu):
    def __init__(self, *args, separator_file, **kwargs):
        self.separator_file = separator_file
        self.edit_manager = editable.EditManager()
        super().__init__(*args, factory_factory=item.ListItemFactory, widget_factory=functools.partial(TandaEditableLabel, self.edit_manager), selection_model=Gtk.SingleSelection, sortable=True, **kwargs)

    def get_filenames(self, selection):
        if self.item_selection_filter_model:
            return [self.separator_file] + [song['file'] for song in self.item_selection_filter_model[0].value['_songs']] + [self.separator_file]
        else:
            return []


class TandaEdit(editstack.WidgetCacheEditStackMixin, TandaSubWidgetMixin, Gtk.Box):
    current_tandaid = GObject.Property()

    def __init__(self, tandas, queue_model, tanda_fields, song_fields, *args, cache, context_menu, **kwargs):
        self.song_view = ViewCacheWithCopyPaste(song_fields, cache=cache, filterable=False)

        super().__init__(*args, **kwargs, orientation=Gtk.Orientation.VERTICAL, edit_stack_view=self.song_view)

        self.tanda_fields = tanda_fields
        self.tanda_view = TandaEditTandaView(tanda_fields, model=tandas, separator_file=self.separator_file)
        self.tanda_view.context_menu.prepend_section(None, context_menu)
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
        self.connect_clean(self.tanda_view.edit_manager, 'edited', self.tanda_edited_cb)

        self.current_tanda = None

        self.song_view.context_menu.append_section(None, self.edit_stack_menu)
        self.tanda_view.context_menu.append_section(None, self.edit_stack_menu)
        self.edit_stack_splicer = self.song_view.splice_keys

    def action_save_cb(self, action, parameter):
        self.activate_action('tanda.save')

    def tanda_edited_cb(self, manager, widget, changes):
        assert self.current_tanda is widget._item
        GLib.idle_add(self.tanda_edited, changes)

    def tanda_edited(self, changes):
        self.current_tanda.edit_stack.hold_transaction()
        for name, value in changes.items():
            self.current_tanda.edit_stack.append_delta(editstack.DeltaItem(name, self.current_tanda.value.get(name), value or None))
        self.current_tanda.edit_stack.release_transaction()

    def tanda_selection_changed_cb(self, model, p, r, a):
        if model:
            self.current_tanda = model[0]
            self.set_edit_stack(self.current_tanda.edit_stack)
        else:
            self.current_tanda = None
            self.set_edit_stack(None)


class TandaView(TandaSubWidgetMixin, ViewCacheWithCopy):
    current_tandaid = GObject.Property()

    def __init__(self, tandas, *args, context_menu, **kwargs):
        super().__init__(*args, **kwargs, item_type=TandaSongItem, sortable=False)
        self.context_menu.prepend_section(None, context_menu)
        self.connect_clean(tandas, 'items-changed', self.tandas_changed)
        item.setup_find_duplicate_items(self.item_model, ['Title', 'Artist', 'Performer', 'Date'], [self.separator_file])
        self.init_tandaid_view(self)

    def tandas_changed(self, tandas, p, r, a):
        filenames = []
        for tanda in tandas:
            tandaid = tanda.tandaid
            for song in tanda.value['_songs']:
                filenames.append((song['file'], tandaid))
            filenames.append((self.separator_file, tandaid))
        self.set_keys(filenames)

    async def _splice_keys(self, task, pos, remove, keys):
        real_keys, tandaids = zip(*keys)
        await self.cache.ensure_keys(real_keys)
        if task is not None:
            await task
        self.item_model.splice_values(pos, remove, (dict(self.cache[key], tandaid=tandaid) for key, tandaid in keys))


class TandaDatabase(db.Database):
    def __init__(self, tanda_model, tanda_fields, song_fields, name, cache):
        self.tanda_model = tanda_model
        self.tanda_fields = tanda_fields
        self.song_fields = song_fields
        self.cache = cache

        self.tanda_field_names = ','.join(map(lambda name: f'tandas.{name}', self.tanda_fields.basic_names))
        self.song_field_names = ','.join(map(lambda name: f'songs.{name}', self.song_fields.basic_names))

        super().__init__(name)

        self.load()

    def setup_database(self, suffix=''):
        self.setup_table(f'tandas{suffix}', 'tandaid INTEGER PRIMARY KEY', self.tanda_fields.basic_names)
        self.setup_table(f'songs{suffix}', 'file TEXT NOT NULL PRIMARY KEY', self.song_fields.basic_names)
        self.connection.cursor().execute(f'CREATE TABLE IF NOT EXISTS tanda_songs{suffix}(tandaid INTEGER NOT NULL, position INTEGER NOT NULL, file TEXT NOT NULL, PRIMARY KEY(tandaid, position), FOREIGN KEY(tandaid) REFERENCES tandas{suffix}, FOREIGN KEY(file) REFERENCES songs{suffix})')

    def clean_database(self):
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
        self.load()

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
            self.update_tanda(tanda)
            self.tanda_fields.set_derived_fields(tanda)
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
        self.tanda_fields.set_derived_fields(tanda)
        return tanda

    @staticmethod
    def _tanda_from_songs(songs):
        def transform(value, patterns):
            for pattern, template in patterns:
                match = re.search(pattern, value)
                if match:
                    return match.expand(template)
            return value

        ARTIST_PATTERNS = [
            # ('^(La Típica Sanata|Otros Aires|.* Orquesta)$', '\\1'),
            # ('^(.* Tango)$', '\\1'),
            ('^(.*), dir\\. (.*) ([^ ]+)$', '\\3, \\2 (\\1)'),
            ('^(Orquesta Típica|Dúo|Cuarteto|Sexteto) (.*)$', '\\2, \\1'),
            ('^(.*) ((?:Di |De |Del )*[^ ]+)$', '\\2, \\1'),
        ]

        LAST_NAME_PATTERNS = [
            ('^(.*) ((?:Di |De |Del )*[^ ]+)$', '\\2'),
        ]

        GENRE_PATTERNS = [
            ('^(Tango|Vals|Milonga) .*$', '\\1'),
        ]

        artists = set()
        performers = set()
        genres = set()
        for song in songs:
            artists.add(transform(song.get('Artist', '???'), ARTIST_PATTERNS))
            genres.add(transform(song.get('Genre', '???'), GENRE_PATTERNS))
            for performer in song.get('Performer', '???').split(', '):
                performers.add(transform(performer, LAST_NAME_PATTERNS))
        tanda = {
            'Artist': '; '.join(sorted(artists)),
            'Performer': ', '.join(sorted(performers)),
            'Genre': ', '.join(sorted(genres)),
            'Last_Modified': str(datetime.date.today()),
        }

        match = re.search('^(.*) \\((.*)\\)$', tanda['Artist'])
        if match:
            tanda['Artist'] = match.group(1)
            tanda['Comment'] = match.group(2)

        return tanda

    # Cleanup stuff

    def get_used_songs(self, ignore):
        with self.connection as cursor:
            query = cursor.execute('SELECT {},file in (SELECT file from tanda_songs) FROM songs'.format(', '.join(self.song_fields.basic_names))).fetchall()
            songs = [self._dict_from_record(t, self.song_fields.basic_names + ['used']) for t in query]

            used_songs = []
            n_unused = 0
            for song in songs:
                if song['used']:
                    used_songs.append(song)
                elif song['file'] not in ignore:
                    n_unused += 1
                    logger.info(_("Deleting '{file}'").format_map(song))
                    cursor.execute('DELETE FROM songs WHERE file=:file', song)

            return used_songs, n_unused

    # Internal

    @staticmethod
    def _make_value_list(names, available_names, exclude=None):
        operations = [f'{name}=:{name}' for name in names if name in available_names and name != exclude] \
            + [f'{name}=NULL' for name in names if name not in available_names and name != exclude]
        return ', '.join(operations)


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
      background: rgb({255 - t * 255 // 10},{t * 255 // 10},0);
    }}
    '''

for p in range(5):
    CSS += f'''
    columnview.tanda-edit > listview > row > cell.property-{p + 1} {{
      background: rgb({p * 255 // 4},{255 // 2},{255 - p * 255 // 4});
    }}
    '''


class __unit__(mixins.UnitConfigMixin, cleanup.CleanupCssMixin, mixins.UnitComponentQueueActionMixin, unit.Unit):
    __gsignals__ = {
        'verify-progress': (GObject.SIGNAL_RUN_LAST, None, (float,)),
    }

    MISSING_SONG_FIELDS = 'Artist', 'Title', 'Date', 'Performer'

    TITLE = _("Tandas")
    KEY = '6'

    def __init__(self, manager):
        super().__init__(manager,
                         config.Dict(
                             paned=TandaWidget.get_paned_config(),
                             fields=field.get_fields_config(),
                         ))

        self.require('fields')
        self.require('database')
        self.require('persistent')
        self.require('search')

        self.css_provider.load_from_string(CSS)

        self.fields = field.FieldFamily(self.config['fields'])
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
        self.fields.register_field(field.Field('Last_Played_Weeks', _("Weeks since last played"), min_width=30, get_value=self.get_last_played_weeks, sort_default=float('inf')))
        self.fields.register_field(field.Field('n_songs', _("Number of songs"), min_width=30, get_value=self.get_n_songs))
        self.fields.register_field(field.Field('Duration', _("Duration"), get_value=lambda tanda: misc.format_time(sum((float(song['duration'])) for song in tanda.get('_songs', [])))))

        self.tanda_model = item.ItemListStore(item_type=TandaItem)
        self.tanda_sorter = Gtk.CustomSorter.new(self.tanda_sort_func)
        self.tanda_sort_model = Gtk.SortListModel(model=self.tanda_model, sorter=self.tanda_sorter)
        self.queue_model = item.ItemListStore(item_type=item.SongItem)

        self.db = TandaDatabase(self.tanda_model, self.fields, self.unit_fields.fields, self.name, self.unit_database.cache)
        self.update_cache_full(None)

        self.connect_clean(self.unit_database, 'cleared', self.update_cache_full)
        self.connect_clean(self.tanda_model, 'items-changed', self.update_cache_partial)

    def cleanup(self):
        del self.db
        self.tanda_sort_model.set_model(None)
        self.tanda_sorter.set_sort_func(None)
        super().cleanup()

    def factory(self):
        component = super().factory()
        component.connect_clean(self, 'verify-progress', self.verify_progress_cb, component)
        return component

    def new_widget(self):
        tanda = TandaWidget(self.tanda_sort_model, self.queue_model, self.config['paned'], self.fields, self.unit_fields.fields, self.unit_database.SEPARATOR_FILE, cache=self.unit_database.cache)

        tanda.connect_clean(self.unit_persistent, 'notify::protect-requested', lambda unit, pspec: unit.protect_requested and tanda.problem_button.set_active(True))
        tanda.add_context_menu_actions(self.generate_db_actions(), 'db', self.TITLE)

        tanda.add_context_menu_actions(self.generate_save_actions(tanda.edit), 'tanda', self.TITLE)
        tanda.edit.tanda_view.add_context_menu_actions(self.generate_edit_actions(tanda.edit), 'edit', self.TITLE)
        tanda.edit.tanda_view.add_context_menu_actions(self.generate_foreign_queue_actions(tanda.edit.tanda_view, False), 'foreign-queue', self.TITLE, protect=self.unit_persistent.protect, prepend=True)
        tanda.connect_clean(tanda.edit.song_view.item_view, 'activate', self.view_activate_cb)

        tanda.view.add_context_menu_actions(self.generate_foreign_queue_actions(tanda.view), 'foreign-queue', self.TITLE, protect=self.unit_persistent.protect, prepend=True)
        tanda.connect_clean(tanda.view.item_view, 'activate', self.view_activate_cb)

        return tanda

    def generate_edit_actions(self, edit):
        yield action.ActionInfo('fill', lambda *args: None, _("Fill field"), ['<Control><Alt>f'])  # Fake action, implemented in TandaListItemFactory
        yield action.ActionInfo('delete', self.action_tanda_delete_cb, _("Delete tanda"), ['<Control>Delete'], activate_args=(edit,))

    def generate_save_actions(self, edit):
        yield action.ActionInfo('save', self.action_tanda_save_cb, activate_args=(edit,))

    @misc.create_task
    async def action_tanda_delete_cb(self, action, parameter, edit):
        if edit.current_tanda is None:
            return
        tanda = edit.current_tanda
        name = ' / '.join(filter(lambda x: x, map(tanda.get_field, ('Artist', 'Years', 'Performer'))))
        if await dialog.MessageDialogAsync(transient_for=edit.get_root(), title=_("Delete tanda"), message=_("Delete {tanda}?").format(tanda=name)).run():
            self.db.delete_tanda(tanda)

    def action_tanda_save_cb(self, action, parameter, edit):
        if edit.current_tanda is None:
            return
        tanda = edit.current_tanda
        new_value = dict(tanda.value, _songs=[self.unit_database.cache[filename] for filename in tanda.edit_stack.items])
        self.fields.set_derived_fields(new_value)
        self.db.update_tanda(dict(new_value, tandaid=tanda.tandaid))
        tanda.value = new_value
        tanda.edit_stack.rebase()
        edit.edit_stack_changed()
        pos = list(self.tanda_model).index(edit.current_tanda)
        self.tanda_model.items_changed(pos, 1, 1)

    def generate_db_actions(self):
        yield action.ActionInfo('verify', self.action_tanda_verify_cb, _("Verify tanda database"), ['<Control><Shift>d'])
        yield action.ActionInfo('cleanup-db', self.action_cleanup_db_cb, _("Cleanup database"))

    @ampd.task
    async def action_tanda_verify_cb(self, action, param):
        window = Gio.Application.get_default().get_active_window()
        await self.ampd.update()
        await self.ampd.idle(ampd.UPDATE)
        await self.ampd.idle(ampd.UPDATE)
        await self.ampd.idle(ampd.IDLE)
        updated = []
        replaced = []
        problem = []
        done = [0]
        used_songs, n_unused = self.db.get_used_songs(ignore=[self.unit_database.SEPARATOR_FILE])

        n_songs = len(used_songs)
        await asyncio.wait([self.verify_song(window, song, n_songs, done, updated, replaced, problem) for song in used_songs])
        logger.info(_("Tanda database checked: {unused} songs unused, {updated} updated, {replaced} replaced, {problem} problematic").format(unused=n_unused, updated=len(updated), replaced=len(replaced), problem=len(problem)))
        self.db.load()

    @ampd.task
    async def verify_song(self, window, song, total, done, updated, replaced, problem):
        real_song = await self.ampd.find('file', song['file'])
        if real_song:
            real_song = real_song[0]
            changed = [(name, song.get(name), real_song.get(name)) for name in self.unit_fields.fields.basic_names if song.get(name) != real_song.get(name)]
            if changed:
                self.db.update_song(real_song)
                logger.info(_("Updating metadata for '{file}': ").format_map(song) + ", ".join("{0} {1} => {2}".format(*t) for t in changed))
                updated.append(song['file'])
        else:
            maybe_song = await self.ampd.find(*sum(([field, song.get(field, '')] for field in self.MISSING_SONG_FIELDS), []))
            if len(maybe_song) == 1:
                logger.info(_("Replacing song:"))
                logger.info("- " + song['file'])
                logger.info("+ " + maybe_song[0]['file'])
                self.db.replace_song(song['file'], maybe_song[0])
                replaced.append((song['file'], maybe_song[0]))
            else:
                logger.info(_("Not sure about '{file}'").format_map(song))
                self.missing_song(window, song['file'], *(song.get(field, '') for field in self.MISSING_SONG_FIELDS))
                problem.append(song)
        done[0] += 1
        self.emit('verify-progress', done[0] / total)

    def verify_progress_cb(self, db, progress, component):
        parts = [self.TITLE]
        if progress < 1:
            parts.append(_("verifying tandas: {progress}%").format(progress=int(progress * 100)))
        component.subtitle = ' '.join(parts)

    @misc.create_task
    async def missing_song(self, window, song_file, *fields):
        search = self.unit_search.new_widget()
        search.entry.set_text(' '.join(f'{name}="{value}"' for name, value in zip(self.MISSING_SONG_FIELDS, fields)))
        search.entry.emit('activate')
        dialog_ = dialog.DialogAsync(transient_for=Gio.Application.get_default().get_active_window(), title=_("Replace {}").format(' / '.join(fields)))
        dialog_.main_box.prepend(search)
        dialog_.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
        dialog_.add_button(_("_OK"), Gtk.ResponseType.OK)
        model = search.main.item_selection_filter_model
        if await dialog_.run() == Gtk.ResponseType.OK and len(model) == 1:
            self.db.replace_song(song_file, model[0].value)
        search.cleanup()

    def action_cleanup_db_cb(self, action, parameter):
        self.db.clean_database()

    def action_tanda_define_cb(self, action, parameter, view):
        filenames = view.get_filenames(True)
        songs = [self.unit_database.cache[name] for name in filenames]
        self.db.new_tanda(songs)

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

    @staticmethod
    def get_n_songs(tanda):
        n = len(tanda.get('_songs'))
        if (n == 4 and tanda.get('Genre').startswith('Tango')) or (n == 3 and tanda.get('Genre') in {'Vals', 'Milonga'}):
            return ''
        else:
            return str(n)
