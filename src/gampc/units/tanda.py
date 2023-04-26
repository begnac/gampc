# coding: utf-8
#
# Graphical Asynchronous Music Player Client
#
# Copyright (C) 2015-2022 Itaï BEN YAACOV
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

from ..util import data
from ..util import db
from ..util import resource
from ..util import unit
from ..util.misc import format_time
from ..util.logger import logger

from ..components import component
from ..components import songlist

from . import search


class Tanda(component.PanedComponent):
    title = _("Tandas")
    name = 'tanda'
    key = '6'
    action_prefix = 'supermod'

    GENRES = ('Tango', 'Vals', 'Milonga', _("Other"), _("All"))
    GENRE_OTHER = len(GENRES) - 2
    GENRE_ALL = len(GENRES) - 1

    current_tandaid = GObject.Property()
    genre_filter = GObject.Property(type=int, default=0)

    def __init__(self, unit):
        super().__init__(unit)

        self.all_tandas = self.filtered_tandas = []
        self.selected_artists = ['*']

        self.left_treeview.set_model(self.left_store)
        self.left_treeview.insert_column_with_attributes(0, _("Artist"), Gtk.CellRendererText(), text=0)
        self.left_treeview.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        self.button_box = Gtk.ButtonBox(orientation=Gtk.Orientation.HORIZONTAL, layout_style=Gtk.ButtonBoxStyle.START, visible=True)
        self.window_actions.add_action(Gio.PropertyAction(name='genre-filter', object=self, property_name='genre-filter'))
        for i, genre in enumerate(self.GENRES):
            button = Gtk.ModelButton(iconic=True, text=genre, centered=True, visible=True, can_focus=False, action_name='supermod.genre-filter', action_target=GLib.Variant.new_int32(i))
            self.button_box.pack_start(button, False, False, 0)
        self.connect('notify::genre-filter', lambda *args: self.filter_tandas(False))

        self.problem_button = Gtk.ToggleButton(image=Gtk.Image(icon_name='object-select-symbolic'), visible=True, can_focus=False, active=unit.unit_persistent.protect_requested, tooltip_text=_("Filter zero note"))
        self.problem_button.connect('toggled', lambda *args: self.filter_tandas(False))

        self.stack = Gtk.Stack(visible=True, transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.switcher = Gtk.StackSwitcher(visible=True, stack=self.stack)

        self.button_box.pack_end(self.problem_button, False, False, 0)
        self.button_box.set_child_secondary(self.problem_button, True)
        self.button_box.pack_end(self.switcher, False, False, 0)
        self.button_box.set_child_secondary(self.switcher, True)

        self.right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=True)
        self.right_box.pack_start(self.button_box, False, False, 0)
        self.right_box.add(self.stack)
        self.add(self.right_box)

        self.edit = TandaEdit(unit)
        self.view = TandaView(unit)
        self.stack.add_titled(self.edit, 'edit', _("Edit tandas"))
        self.stack.add_titled(self.view, 'view', _("View tandas"))
        self.subcomponents = [self.edit, self.view]
        for c in self.subcomponents:
            self.bind_property('current-tandaid', c, 'current-tandaid', GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)
        self.subcomponent_index = 0

        self.signal_handler_connect(self.unit.db, 'changed', self.db_changed_cb)
        self.signal_handler_connect(self.unit.db, 'verify-progress', self.db_verify_progress_cb)
        self.signal_handler_connect(self.unit.db, 'missing-song', self.db_missing_song_cb)

        self.window_actions.add_action(resource.Action('tanda-switch-subcomponent', self.action_subcomponent_next_cb))
        self.window_actions.add_action(resource.Action('tanda-verify', self.unit.db.action_tanda_verify_cb))
        self.window_actions.add_action(resource.Action('tanda-cleanup-db', self.unit.db.action_cleanup_db_cb))

        self.signal_handler_connect(self.unit.unit_persistent, 'notify::protect-requested', lambda unit_persistent, param_spec: unit_persistent.protect_requested and self.problem_button.set_active(True))

        self.read_db()

    def set_window(self, win=None):
        super().set_window(win)
        self.subcomponents[self.subcomponent_index].set_window(self.win)

    def init_left_store(self):
        return Gtk.ListStore(str)

    def action_subcomponent_next_cb(self, action, param):
        self.subcomponents[self.subcomponent_index].set_window()
        self.subcomponent_index = (self.subcomponent_index + 1) % len(self.subcomponents)
        self.stack.set_visible_child(self.subcomponents[self.subcomponent_index])
        self.subcomponents[self.subcomponent_index].set_window(self.win)

    def tanda_filter_holds(self, tanda):
        if tanda.get('Note') == '0' and self.problem_button.get_active():
            return False
        if self.genre_filter == self.GENRE_ALL:
            return True

        genre = tanda.get('Genre', '')

        def test(i):
            return self.GENRES[i] in genre

        return test(self.genre_filter) if self.genre_filter < self.GENRE_OTHER else not any(test(i) for i in range(self.GENRE_OTHER))

    def read_db(self):
        self.all_tandas = list(self.unit.db.get_tandas())
        self.filter_tandas()

    def filter_tandas(self, sort=True):
        if sort:
            self.all_tandas.sort(key=self.tanda_key_func)
        self.filtered_tandas = list(filter(self.tanda_filter_holds, self.all_tandas))
        artists = sorted(set(tanda.get('Artist', '') for tanda in self.filtered_tandas))
        selection = self.left_treeview.get_selection()
        selection.handler_block_by_func(self.left_treeview_selection_changed_cb)
        selection.unselect_all()
        self.left_store_set_rows(['*'] + artists)
        for i, artist in enumerate(['*'] + artists):
            if artist in self.selected_artists:
                selection.select_path(Gtk.TreePath.new_from_indices([i]))
        selection.handler_unblock_by_func(self.left_treeview_selection_changed_cb)
        self.filter_artists()

    @staticmethod
    def tanda_key_func(tanda):
        return (tanda.get('Artist', ''),
                99 if 'Genre' not in tanda else 1 if 'Tango' in tanda['Genre'] else 2 if 'Vals' in tanda['Genre'] else 3 if 'Milonga' in tanda['Genre'] else 4,
                tanda['Years'][2:] if 'Years' in tanda and tanda['Years'].startswith('* ') else tanda.get('Years', ''),
                tanda.get('Performer', ''),
                tanda.get('First_Song', ''),)

    def left_treeview_selection_changed_cb(self, *args):
        if not self.filtered_tandas:
            return
        store, paths = self.left_treeview.get_selection().get_selected_rows()
        self.selected_artists = [store.get_value(store.get_iter(path), 0) for path in paths] or ['*']
        self.filter_artists()

    def filter_artists(self):
        tandas = [tanda for tanda in self.filtered_tandas if '*' in self.selected_artists or tanda.get('Artist') in self.selected_artists]
        for c in self.subcomponents:
            c.set_tandas(tandas)
            c.set_cursor_tandaid(self.current_tandaid)

    def db_changed_cb(self, db, tandaid):
        if tandaid == -1:
            return self.read_db()

        for tanda in self.all_tandas:
            if tanda.get('tandaid') == tandaid:
                if not self.unit.db.reread_tanda(tanda):
                    self.all_tandas.remove(tanda)
                break
        else:
            tanda = self.unit.db.get_tanda(tandaid)
            if tanda:
                self.all_tandas.append(tanda)
        self.filter_tandas()

    def db_verify_progress_cb(self, db, progress):
        if progress < 1:
            self.status = _("verifying tandas: {progress}%").format(progress=int(progress * 100))
        else:
            self.status = None

    def db_missing_song_cb(self, db, song_file, *fields):
        search_window = Gtk.Window(destroy_with_parent=True, transient_for=self.win, window_position=Gtk.WindowPosition.CENTER_ON_PARENT,
                                   default_width=500, default_height=500,
                                   title=_("Replace {}").format(' / '.join(fields)))
        search_window.update_title = lambda *args: None
        search_component = search.Search(self.unit)
        search_component.entry.set_text(' '.join('{}="{}"'.format(field, fields[i]) for i, field in enumerate(db.MISSING_SONG_FIELDS)))
        button_box = Gtk.ButtonBox(visible=True, layout_style=Gtk.ButtonBoxStyle.CENTER)
        cancel_button = Gtk.Button(visible=True, label=_("_Cancel"), use_underline=True)
        cancel_button.connect('clicked', lambda button: button.get_toplevel().destroy())
        button_box.add(cancel_button)
        ok_button = Gtk.Button(visible=True, label=_("_OK"), use_underline=True)
        ok_button.connect('clicked', self.db_missing_song_ok_cb, db, search_component, song_file)
        button_box.add(ok_button)
        search_component.get_child().add(button_box)
        search_window.add(search_component)
        search_window.present()

    @staticmethod
    def db_missing_song_ok_cb(button, db, search_component, song_file):
        path, focus = search_component.treeview.get_cursor()
        if path:
            i = search_component.store.get_iter(path)
            song = search_component.store.get_record(i).get_data()
            db.replace_song(song_file, song)
            db.emit('changed', -1)
            search_component.get_toplevel().destroy()


class TandaSubComponent(component.Component):
    current_tandaid = GObject.Property()

    def __init__(self, unit):
        super().__init__(unit)
        self.connect('map', lambda self: self.set_cursor_tandaid(self.current_tandaid))
        self.color = Gdk.RGBA()

    def init_tandaid_treeview(self, treeview):
        self.tandaid_treeview = treeview
        self.tandaid_store = treeview.get_model()
        self.tandaid_treeview.connect('cursor-changed', self.tandaid_cursor_changed_cb)

    def set_cursor_tandaid(self, tandaid):
        for i, p, row in self.tandaid_store:
            if row.tandaid == tandaid:
                self.tandaid_treeview.set_cursor(p)
                self.tandaid_treeview.scroll_to_cell(p, None, False)
                return

    def tandaid_cursor_changed_cb(self, treeview):
        path, column = self.tandaid_treeview.get_cursor()
        self.current_tandaid = path and self.tandaid_store.get_record(self.tandaid_store.get_iter(path)).tandaid


RGBA_PURPLE = Gdk.RGBA()
RGBA_PINK = Gdk.RGBA()
RGBA_YELLOW = Gdk.RGBA()
RGBA_PURPLE.parse('purple')
RGBA_PINK.parse('pink')
RGBA_YELLOW.parse('yellow')


class TandaEdit(TandaSubComponent, songlist.SongListWithEditDelNew):
    name = 'tanda-edit'

    duplicate_field = '_duplicate_edit'

    def __init__(self, unit):
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=True)

        super().__init__(unit)

        self.current_tanda = None
        self.current_tanda_path = None

        self.window_actions.add_action(resource.Action('tanda-delete', self.action_tanda_delete_cb))
        self.window_actions.add_action(resource.Action('tanda-reset', self.action_tanda_reset_cb))
        self.window_actions.add_action(resource.Action('tanda-reset-field', self.action_tanda_field_cb))
        self.window_actions.add_action(resource.Action('tanda-fill-field', self.action_tanda_field_cb))

        self.tanda_treeview = data.RecordTreeView(self.unit.db.fields, self.tanda_data_func, True)
        self.tanda_treeview.set_name('tanda-treeview')
        self.tanda_treeview.connect('button-press-event', self.tanda_treeview_button_press_event_cb)
        self.setup_context_menu('tanda-edit.left-context', self.tanda_treeview)
        self.init_tandaid_treeview(self.tanda_treeview)

        for name in self.unit.db.fields.basic_names:
            col = self.tanda_treeview.cols[name]
            col.renderer.set_property('editable', True)
            col.renderer.connect('editing-started', self.renderer_editing_started_cb, name)
        self.tanda_store = self.tanda_treeview.get_model()
        self.tanda_treeview.connect('cursor-changed', self.tanda_treeview_cursor_changed_cb)
        self.tanda_filter = data.TreeViewFilter(self.unit.unit_misc, self.tanda_treeview)

        self.window_actions.remove('filter')
        self.window_actions.add_action(Gio.PropertyAction(name='filter', object=self.tanda_filter, property_name='active'))

        self.treeview.set_vexpand(False)
        self.treeview_filter.scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)

        self.box.pack_start(self.tanda_filter, True, True, 0)
        super().add(self.box)

        self.queue = []

    def add(self, widget):
        self.box.pack_end(widget, False, False, 0)

    @ampd.task
    async def client_connected_cb(self, client):
        while True:
            self.queue = await self.ampd.playlistinfo()
            if self.current_tanda:
                self.find_duplicates(self.queue + self.current_tanda._songs, ['Title'])
                self.treeview.queue_draw()
            await self.ampd.idle(ampd.PLAYLIST)

    def tanda_data_func(self, column, renderer, store, i, j):
        tanda = store.get_record(i)
        if tanda._modified:
            renderer.set_property('font', 'bold italic')
        else:
            renderer.set_property('font', None)

        rgba = self.cell_background(tanda, column.field.name)

        if rgba is None:
            renderer.set_property('background-set', False)
        else:
            renderer.set_property('background-rgba', rgba)
            renderer.set_property('background-set', True)

    @staticmethod
    def cell_background(tanda, name):
        if name in tanda.get_data():
            if 'Last_Played' in name and 'Last_Played_Weeks' in tanda.get_data():
                t = min(tanda.Last_Played_Weeks / 10.0, 1.0)
                return Gdk.RGBA(1.0 - t, t, 0.0, 1.0)
            elif name in ('Rhythm', 'Energy', 'Speed', 'Level'):
                t = min((int(tanda.get_data()[name]) - 1) / 4.0, 1.0)
                return Gdk.RGBA(t, 0.5, 1.0 - t, 1.0)
            elif name == 'Emotion':
                if tanda.Emotion == 'T':
                    return RGBA_PURPLE
                elif tanda.Emotion == 'R':
                    return RGBA_PINK
                elif tanda.Emotion == 'J':
                    return RGBA_YELLOW
            elif name in ('Genre',):
                if tanda.Genre == 'Vals':
                    return RGBA_PINK
                elif tanda.Genre == 'Milonga':
                    return RGBA_YELLOW

    def set_modified(self, modified=True):
        self.current_tanda._modified = modified
        self.tanda_treeview.queue_draw()

    def set_tandas(self, tandas):
        self.tanda_store.set_rows(tandas)
        self.current_tanda = None
        self.set_current_tanda()

    def tanda_treeview_cursor_changed_cb(self, *args):
        self.current_tanda_path, column = self.tanda_treeview.get_cursor()
        self.set_current_tanda()

    def set_current_tanda(self):
        if self.current_tanda:
            self.current_tanda._songs = [song.get_data() for i, p, song in self.store]
        if self.current_tanda_path is None:
            self.current_tanda = None
            self.set_records([])
        else:
            self.current_tanda = self.tanda_store.get_record(self.tanda_store.get_iter(self.current_tanda_path))
            self.find_duplicates(self.queue + self.current_tanda._songs, ['Title'])
            self.set_records(self.current_tanda._songs)

    def renderer_editing_started_cb(self, renderer, editable, path, name):
        editable.connect('editing-done', self.editing_done_cb, path, name)
        self.unit.unit_misc.block_fragile_accels = True
        self.tanda_treeview.handler_block_by_func(self.tanda_treeview_button_press_event_cb)

    def editing_done_cb(self, editable, path, name):
        self.tanda_treeview.handler_unblock_by_func(self.tanda_treeview_button_press_event_cb)
        self.unit.unit_misc.block_fragile_accels = False
        if editable.get_property('editing-canceled'):
            return
        value = editable.get_text() or None
        if value != getattr(self.current_tanda, name):
            if value:
                setattr(self.current_tanda, name, value)
            else:
                delattr(self.current_tanda, name)
            self.set_modified()

    def tanda_treeview_button_press_event_cb(self, tanda_treeview, event):
        pos = self.tanda_treeview.get_path_at_pos(event.x, event.y)
        if not pos:
            return False
        path, col, cx, xy = pos
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 1:
            selection = self.tanda_treeview.get_selection()
            if event.state & Gdk.ModifierType.CONTROL_MASK:
                if selection.path_is_selected(path):
                    selection.unselect_path(path)
                else:
                    selection.select_path(path)
            elif event.state & Gdk.ModifierType.SHIFT_MASK:
                oldpath, column = self.tanda_treeview.get_cursor()
                if oldpath:
                    selection.select_range(oldpath, path)
                else:
                    selection.select_path(path)
            else:
                self.tanda_treeview.set_cursor_on_cell(path, col, col.renderer, False)
                self.tanda_treeview.grab_focus()
            return True
        elif event.type == Gdk.EventType._2BUTTON_PRESS and event.button == 1:
            self.tanda_treeview.set_cursor(path, col, True)
            return True

    def action_tanda_delete_cb(self, action, parameter):
        path, column = self.tanda_treeview.get_cursor()
        if not path:
            return
        i = self.tanda_store.get_iter(path)
        tanda = self.tanda_store.get_record(i)
        title = ' / '.join(filter(lambda x: x, (tanda.Artist, tanda.Years, tanda.Performer)))
        dialog = Gtk.Dialog(parent=self.win, title=_("Delete tanda"))
        dialog.get_content_area().add(Gtk.Label(label=_("Delete {tanda}?").format(tanda=title), visible=True))
        dialog.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("_OK"), Gtk.ResponseType.OK)
        reply = dialog.run()
        dialog.destroy()
        if reply == Gtk.ResponseType.OK:
            self.unit.db.delete_tanda(tanda.tandaid)

    def get_filenames(self, selection=True):
        if selection:
            return super().get_filenames(True)
        else:
            store, paths = self.tanda_treeview.get_selection().get_selected_rows()
            return sum(([song['file'] for song in store.get_record(store.get_iter(path))._songs] + [self.unit.unit_server.SEPARATOR_FILE] for path in paths), [self.unit.unit_server.SEPARATOR_FILE])

    def action_save_cb(self, action, parameter):
        if self.current_tanda:
            self.current_tanda._songs = [song.get_data() for i, p, song in self.store]
        store, paths = self.tanda_treeview.get_selection().get_selected_rows()
        for path in paths:
            tanda = store.get_record(store.get_iter(path))
            tanda._songs = [song for song in tanda._songs if song.get('_status') != self.RECORD_DELETED]
            self.unit.db.update_tanda(tanda.get_data())

    def action_reset_cb(self, action, parameter):
        self.tanda_filter.filter_.set_data({})
        self.tanda_filter.active = False
        self.tanda_store.set_sort_column_id(-1, Gtk.SortType.ASCENDING)

    def action_tanda_reset_cb(self, action, parameter):
        self.unit.db.reread_tanda(self.current_tanda.get_data())
        self.set_records(self.current_tanda._songs)
        self.tanda_treeview.queue_draw()

    def action_tanda_field_cb(self, action, parameter):
        path, column = self.tanda_treeview.get_cursor()
        if not path:
            return
        reset = 'reset' in action.get_name()
        tanda = self.tanda_store.get_record(self.tanda_store.get_iter(path))
        name = column.field.name
        alt_tanda = self.unit.db.get_tanda(tanda.tandaid) if reset else self.unit.db.tanda_from_songs([song for song in tanda._songs if song.get('_status') != self.RECORD_DELETED])
        if name in alt_tanda:
            setattr(tanda, name, alt_tanda[name])
        elif reset:
            try:
                delattr(tanda, name)
            except AttributeError:
                pass
        if not reset:
            self.set_modified()
        self.tanda_treeview.queue_draw()

    def action_copy_delete_cb(self, action, parameter):
        focus = self.win.get_focus()
        if focus == self.tanda_treeview and action.get_name() == 'copy':
            path, column = focus.get_cursor()
            if column:
                name = column.field.name
                Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(repr({name: self.tanda_store.get_record(self.tanda_store.get_iter(path)).get_data()[name]}), -1)
        elif isinstance(focus, Gtk.Entry):
            if action.get_name() in ['copy', 'cut']:
                focus.emit(action.get_name() + '-clipboard')
            else:
                focus.emit('delete-from-cursor', Gtk.DeleteType.CHARS, 1)
        else:
            super().action_copy_delete_cb(action, parameter)

    def action_paste_cb(self, action, parameter):
        focus = self.win.get_focus()
        if isinstance(focus, Gtk.Entry):
            focus.emit('paste-clipboard')
        else:
            Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).request_text(self.clipboard_paste_cb, action.get_name().endswith('before'))

    def clipboard_paste_cb(self, clipboard, raw, before):
        focus = self.win.get_focus()
        if focus == self.tanda_treeview:
            store, paths = focus.get_selection().get_selected_rows()
            to_paste = ast.literal_eval(raw)
            if not isinstance(to_paste, dict):
                return
            for path in paths:
                tanda = self.tanda_store.get_record(self.tanda_store.get_iter(path)).get_data()
                for name, value in to_paste.items():
                    if value:
                        tanda[name] = value
                    else:
                        tanda.pop(name, None)
                tanda['_modified'] = True
            focus.queue_draw()
        else:
            self.treeview.clipboard_paste_cb(clipboard, raw, before)

    def set_records(self, songs):
        super().set_records(songs)
        self.treeview.set_size_request(-1, max(26, 25 + self.store.iter_n_children() * 27))


class TandaView(TandaSubComponent, songlist.SongList):
    name = 'tanda-view'

    duplicate_test_columns = ['Title', 'Artist', 'Performer', 'Date']
    duplicate_field = '_duplicate_view'

    def __init__(self, unit):
        super().__init__(unit)
        self.init_tandaid_treeview(self.treeview)

    def set_tandas(self, tandas):
        songs = [self.unit.unit_server.separator_song]
        songs[0]['tandaid'] = None
        for tanda in tandas:
            tandaid = tanda['tandaid']
            for song in tanda['_songs'] + [self.unit.unit_server.separator_song]:
                song['tandaid'] = tandaid
                songs.append(song)
        self.set_records(songs)


class TandaDatabase(GObject.Object, db.Database):
    __gsignals__ = {
        'changed': (GObject.SIGNAL_RUN_LAST, None, (int,)),
        'verify-progress': (GObject.SIGNAL_RUN_LAST, None, (float,)),
        'missing-song': (GObject.SIGNAL_RUN_LAST, None, (str, str, str, str, str)),
    }

    MISSING_SONG_FIELDS = 'Artist', 'Title', 'Date', 'Performer'

    def __init__(self, fields, unit):
        self.fields = fields
        self.unit = unit
        db.Database.__init__(self, Tanda.name)
        super().__init__()
        self.ampd = unit.ampd.sub_executor()

    def setup_database(self, suffix=''):
        self.setup_table('tandas' + suffix, 'tandaid INTEGER PRIMARY KEY', self.fields.basic_names)
        self.setup_table('songs' + suffix, 'file TEXT NOT NULL PRIMARY KEY', self.unit.unit_songlist.fields.basic_names)
        self.connection.cursor().execute('CREATE TABLE IF NOT EXISTS tanda_songs{0}(tandaid INTEGER NOT NULL, position INTEGER NOT NULL, file TEXT NOT NULL, PRIMARY KEY(tandaid, position), FOREIGN KEY(tandaid) REFERENCES tandas{0}, FOREIGN KEY(file) REFERENCES songs{0})'.format(suffix))

    def action_cleanup_db_cb(self, action, param):
        with self.connection:
            cursor = self.connection.cursor()
            self.setup_database('_tmp')
            cursor.execute('INSERT INTO songs_tmp({0}) SELECT {0} FROM songs WHERE file IN (SELECT file FROM tanda_songs) ORDER BY file'.format(','.join(self.unit.unit_songlist.fields.basic_names)))
            for tanda in cursor.execute('SELECT {} FROM tandas ORDER BY Artist'.format(','.join(self.fields.basic_names + ['tandaid']))).fetchall():
                old_tandaid = tanda[-1]
                tanda = tanda[:-1]
                cursor.execute('INSERT INTO tandas_tmp({}) VALUES({})'.format(','.join(self.fields.basic_names), ','.join(['?'] * len(tanda))), tanda)
                tandaid = self.connection.last_insert_rowid()
                cursor.execute('INSERT INTO tanda_songs_tmp(tandaid,position,file) SELECT ?,position,file FROM tanda_songs WHERE tandaid=? ORDER BY position', (tandaid, old_tandaid))
            cursor.execute('DROP TABLE tanda_songs')
            cursor.execute('DROP TABLE tandas')
            cursor.execute('DROP TABLE songs')
            cursor.execute('ALTER TABLE tanda_songs_tmp RENAME TO tanda_songs')
            cursor.execute('ALTER TABLE tandas_tmp RENAME TO tandas')
            cursor.execute('ALTER TABLE songs_tmp RENAME TO songs')

    def add_song(self, song):
        cursor = self.connection.cursor()
        if cursor.execute('SELECT ? NOT IN (SELECT file FROM songs)', (song['file'],)).fetchone()[0]:
            with self.connection:
                cursor.execute('INSERT INTO songs(file) VALUES(:file)', song)
                self.update_song(song)

    def update_song(self, song):
        self.connection.cursor().execute('UPDATE songs SET {} WHERE file=:file'.format(self._make_value_list(self.unit.unit_songlist.fields.basic_names, exclude='file')), song)

    def replace_song(self, old_file, new_song):
        self.add_song(new_song)
        self.connection.cursor().execute('UPDATE tanda_songs SET file=? WHERE file=?', (new_song['file'], old_file))
        self.connection.cursor().execute('DELETE FROM songs WHERE file=?', (old_file,))

    def set_tanda_songs(self, tandaid, songs):
        cursor = self.connection.cursor()
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
        query = self.connection.cursor().execute('SELECT tandaid,{} FROM tandas'.format(','.join(self.fields.basic_names)))
        return map(self._get_tanda_from_tuple, query)

    def get_tanda(self, tandaid):
        t = self.connection.cursor().execute('SELECT tandaid, {} FROM tandas WHERE tandaid=?'.format(','.join(self.fields.basic_names)), (tandaid,)).fetchone()
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
        tanda = self._tuple_to_dict(t, ['tandaid'] + self.fields.basic_names)
        query = self.connection.cursor().execute('SELECT {} FROM tanda_songs,songs USING(file) WHERE tanda_songs.tandaid=?'.format(', songs.'.join(['tanda_songs.position'] + self.unit.unit_songlist.fields.basic_names)), (tanda['tandaid'],))
        tanda['_songs'] = [self._tuple_to_dict(s, ['_position'] + self.unit.unit_songlist.fields.basic_names) for s in query]
        self.fields.record_set_fields(tanda)
        return tanda

    def update_tanda(self, tanda):
        with self.connection:
            self.connection.cursor().execute('UPDATE tandas SET {} WHERE tandaid=:tandaid'.format(', '.join([name + '=:' + name for name in self.fields.basic_names if name != 'tandaid'])), tanda)
            tandaid = tanda['tandaid']
            self.set_tanda_songs(tandaid, tanda['_songs'])
        self.emit('changed', tandaid)

    def delete_tanda(self, tandaid):
        with self.connection:
            self.connection.cursor().execute('DELETE FROM tanda_songs WHERE tandaid=?; DELETE FROM tandas WHERE tandaid=?', (tandaid, tandaid))
        self.emit('changed', tandaid)

    @staticmethod
    def tanda_from_songs(songs):
        fields = (('ArtistSortName', '???'),
                  ('Genre', '???'),
                  ('PerformersLastNames', '???'))
        merged = {field: [song.get(field, default) for song in songs] for field, default in fields}
        merged['Genre'] = [genre if genre.split(' ', 1)[0] not in ('Tango', 'Vals', 'Milonga') else genre.split(' ', 1)[0] for genre in merged['Genre']]
        sorted_merged = {field: sorted(set(merged[field])) for field, default in fields}
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
    def _make_value_list(names, exclude=None, separator=', ', operator='='):
        return separator.join(name + operator + ':' + name for name in names if name != exclude)

    def action_tanda_define_cb(self, songlist, action, parameter):
        songs, rows = songlist.treeview.get_selection_rows()
        tanda = self.tanda_from_songs(songs)
        with self.connection:
            self.connection.cursor().execute('INSERT INTO tandas DEFAULT VALUES')
            tanda['tandaid'] = tandaid = self.connection.last_insert_rowid()
            self.connection.cursor().execute('UPDATE tandas SET {} WHERE tandaid=:tandaid'.format(self._make_value_list(self.fields.basic_names)), tanda)
            self.set_tanda_songs(tandaid, songs)
        self.emit('changed', tandaid)

    @ampd.task
    async def action_tanda_verify_cb(self, action, param):
        await self.ampd.idle(ampd.CONNECT)
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
            query = self.connection.cursor().execute('SELECT {},file in (SELECT file from tanda_songs) FROM songs'.format(', '.join(self.unit.unit_songlist.fields.basic_names))).fetchall()
            songs = [self._tuple_to_dict(t, self.unit.unit_songlist.fields.basic_names + ['used']) for t in query]
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
            changed = [(name, song.get(name), real_song[0].get(name)) for name in self.unit.unit_songlist.fields.basic_names if song.get(name) != real_song[0].get(name)]
            if changed:
                self.update_song(real_song[0])
                logger.info(_("Updating metadata for '{file}': ").format_map(song) + ", ".join("{0} {1} => {2}".format(*t) for t in changed))
                updated.append(song['file'])
        else:
            maybe_song = await self.ampd.find(*sum(([field, song.get(field, '')] for field in self.MISSING_SONG_FIELDS), []))
            if len(maybe_song) == 1:
                logger.info(_("Replacing song:"))
                logger.info("- " + song['file'])
                logger.info("+ " + maybe_song[0]['file'])
                self.replace_song(song['file'], maybe_song[0])
                replaced.append((song['file'], maybe_song[0]))
            else:
                logger.info(_("Not sure about '{file}'").format_map(song))
                self.emit('missing-song', song['file'], *(song.get(field, '') for field in self.MISSING_SONG_FIELDS))
                problem.append(song)
        done[0] += 1
        self.emit('verify-progress', done[0] / total)


def get_last_played_weeks(tanda):
    if 'Last_Played' in tanda and tanda['Last_Played']:
        try:
            return (datetime.date.today() - datetime.date(*map(int, tanda['Last_Played'].split('-')))).days // 7
        except Exception:
            pass
    return None


class __unit__(unit.UnitMixinCss, songlist.UnitMixinPanedSongList, unit.Unit):
    COMPONENT_CLASS = Tanda
    CSS = b'#tanda-treeview.view { outline-width: 4px; outline-style: solid; }'

    def __init__(self, name, manager):
        super().__init__(name, manager)

        self.fields = data.FieldFamily(self.config.fields)
        self.fields.register_field(data.Field('Artist', _("Artist")))
        self.fields.register_field(data.Field('Genre', _("Genre")))
        self.fields.register_field(data.Field('Years_Min', visible=False, get_value=lambda tanda: min(song.get('Date', '').split('-', 1)[0] for song in tanda['_songs']) or '????' if tanda.get('_songs') else None))
        self.fields.register_field(data.Field('Years_Max', visible=False, get_value=lambda tanda: max(song.get('Date', '').split('-', 1)[0] for song in tanda['_songs']) or '????' if tanda.get('_songs') else None))
        self.fields.register_field(data.Field('Years', _("Years"), get_value=lambda tanda: ('\'{}'.format(tanda['Years_Min'][2:]) if tanda['Years_Min'] == tanda['Years_Max'] else '\'{}-\'{}'.format(tanda['Years_Min'][2:], tanda['Years_Max'][2:])) if 'Years_Min' in tanda and 'Years_Max' in tanda else '????'))
        self.fields.register_field(data.Field('First_Song', _("First song"), get_value=lambda tanda: tanda['_songs'][0]['Title'] if '_songs' in tanda else '???'))
        self.fields.register_field(data.Field('Performer', _("Performer")))
        self.fields.register_field(data.Field('Comment', _("Comment")))
        self.fields.register_field(data.Field('Description', _("Description")))
        self.fields.register_field(data.Field('Note', _("Note"), min_width=30))
        self.fields.register_field(data.Field('Rhythm', _("Rhythm"), min_width=30))
        self.fields.register_field(data.Field('Energy', _("Energy"), min_width=30))
        self.fields.register_field(data.Field('Speed', _("Speed"), min_width=30))
        self.fields.register_field(data.Field('Emotion', _("Emotion"), min_width=30))

        # self.fields.register_field(data.Field('Drama', _("Drama"), min_width=30))
        # self.fields.register_field(data.Field('Romance', _("Romance"), min_width=30))
        self.fields.register_field(data.Field('Level', _("Level"), min_width=30))

        self.fields.register_field(data.Field('Last_Modified', _("Last modified")))
        self.fields.register_field(data.Field('Last_Played', _("Last played")))
        self.fields.register_field(data.Field('Last_Played_Weeks', _("Weeks since last played"), min_width=30, get_value=get_last_played_weeks))
        self.fields.register_field(data.Field('n_songs', _("Number of songs"), min_width=30, get_value=lambda tanda: 0 if not tanda.get('_songs') else None if (len(tanda.get('_songs')) == 4 and tanda.get('Genre').startswith('Tango')) or (len(tanda.get('_songs')) == 3 and tanda.get('Genre') in {'Vals', 'Milonga'}) else len(tanda.get('_songs'))))
        self.fields.register_field(data.Field('Duration', _("Duration"), get_value=lambda tanda: format_time(sum((int(song['Time'])) for song in tanda.get('_songs', [])))))

        self.db = TandaDatabase(self.fields, self)

        self.add_resources(
            'app.action',
            resource.ActionModel('tanda-verify', self.db.action_tanda_verify_cb),
            resource.ActionModel('tanda-cleanup-db', self.db.action_cleanup_db_cb),
        )

        self.add_resources(
            'app.menu',
            resource.MenuAction('edit/component', 'mod.tanda-fill-field', _("Fill tanda field"), ['<Control>z']),
            resource.MenuAction('edit/component', 'mod.tanda-reset-field', _("Reset tanda field"), ['<Control><Shift>z']),
            resource.MenuAction('edit/component', 'mod.tanda-reset', _("Reset tanda"), ['<Control><Shift>r']),
            resource.MenuAction('edit/component', 'mod.tanda-delete', _("Delete tanda"), ['<Control>Delete']),
            resource.MenuAction('edit/component', 'supermod.tanda-switch-subcomponent', _("Switch tanda view mode"), ['<Control>Tab']),
            resource.MenuAction('edit/component', 'supermod.tanda-verify', _("Verify tanda database"), ['<Control><Shift>d']),
            resource.MenuAction('edit/component', 'supermod.tanda-cleanup-db', _("Cleanup database")),
        )

        self.add_resources(
            'songlist.action',
            resource.ActionModel('tanda-define', self.db.action_tanda_define_cb),
        )

        self.add_resources(
            'songlist.context.menu',
            resource.MenuAction('other', 'mod.tanda-define', _("Define tanda")),
        )

        self.add_resources(
            'tanda-edit.left-context.menu',
            resource.MenuAction('edit', 'mod.tanda-delete', _("Delete tanda")),
        )

        self.setup_menu('tanda-edit', 'context', ['songlistbase', 'songlist'])
        self.setup_menu('tanda-edit', 'left-context', ['songlistbase', 'songlist'])
        self.setup_menu('tanda-view', 'context', ['songlistbase', 'songlist'])

    def shutdown(self):
        del self.db
        super().shutdown()
