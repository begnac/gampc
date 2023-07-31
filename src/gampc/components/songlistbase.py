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


from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import Gtk

import ampd

from ..util import resource
from ..ui import view
from . import component


class SongListBase(component.Component):
    editable = False
    sortable = False
    duplicate_test_columns = []
    duplicate_field = '_duplicate'

    RECORD_NEW = 1
    RECORD_DELETED = 2
    RECORD_MODIFIED = 3
    RECORD_UNDEFINED = 4

    STATUS_PROPERTIES = ('background-rgba', 'font', 'strikethrough')
    STATUS_PROPERTY_TABLE = {
        RECORD_NEW: (Gdk.RGBA(0.0, 1.0, 0.0, 1.0), 'bold', None),
        RECORD_DELETED: (Gdk.RGBA(1.0, 0.0, 0.0, 1.0), 'italic', True),
        RECORD_MODIFIED: (Gdk.RGBA(1.0, 1.0, 0.0, 1.0), None, None),
        RECORD_UNDEFINED: (None, 'bold italic', None),
    }

    def __init__(self, unit, *args, **kwargs):
        super().__init__(unit, *args, **kwargs)

        self.widget = self.view = view.View(self.fields, self.sortable)
        self.widget.record_view.add_css_class('songlistbase')

        self.songlistbase_actions = self.add_actions_provider('songlistbase')
        self.songlistbase_actions.add_action(resource.Action('reset', self.action_reset_cb))
        self.songlistbase_actions.add_action(resource.Action('copy', self.action_copy_delete_cb))

        if self.editable:
            self.songlistbase_actions.add_action(resource.Action('paste', self.action_paste_cb))
            self.songlistbase_actions.add_action(resource.Action('paste-before', self.action_paste_cb))
            self.songlistbase_actions.add_action(resource.Action('delete', self.action_copy_delete_cb))
            self.songlistbase_actions.add_action(resource.Action('cut', self.action_copy_delete_cb))
            self.signal_handler_connect(self.widget.store, 'items-changed', self.records_changed_cb)

        self.set_editable(True)

        self.songlistbase_actions.add_action(Gio.PropertyAction(name='filter', object=self.widget, property_name='filtering'))

        # self.setup_context_menu(f'{self.name}.context', self.view)
        self.widget.record_view.connect('activate', self.view_activate_cb)

        self.widget.bind_hooks.append(self.duplicate_bind_hook)

    def shutdown(self):
        del self.songlistbase_actions
        super().shutdown()

    def set_editable(self, editable):
        return
        dndtargets = [Gtk.TargetEntry.new(self.DND_TARGET, Gtk.TargetFlags(0), 0)]

        if self.record_new_cb != NotImplemented:
            if editable:
                self.view.drag_dest_set(Gtk.DestDefaults.DROP, dndtargets, Gdk.DragAction.MOVE | Gdk.DragAction.COPY)
            else:
                self.view.drag_dest_unset()

        if self.record_delete_cb != NotImplemented and editable:
            self.view.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, dndtargets, Gdk.DragAction.MOVE | Gdk.DragAction.COPY)
        else:
            self.view.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, dndtargets, Gdk.DragAction.COPY)

        for name in ['paste', 'paste-before', 'delete', 'cut']:
            action_ = self.songlistbase_actions.lookup(name)
            if action_ is not None:
                action_.set_enabled(editable)

    def action_copy_delete_cb(self, action, parameter):
        data, positions = self.view.get_selection()
        if action.get_name() in ['copy', 'cut']:
            self.widget.get_clipboard().set_content(Gdk.ContentProvider.new_for_value(repr(data)))
        if action.get_name() in ['delete', 'cut']:
            for i in positions.reversed():
                self.delete_record(i)

    def action_paste_cb(self, action, parameter):
        self.widget.get_clipboard().read_text_async(None, self.action_paste_finish_cb)

    def action_paste_finish_cb(self, clipboard, result):
        result = clipboard.read_text_finish(result)
        # Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).request_text(self.view.clipboard_paste_cb, action.get_name().endswith('before'))

    @ampd.task
    async def view_activate_cb(self, view, position):
        if self.unit.unit_persistent.protect_active:
            return
        filename = self.widget.store.get_item(position).file
        records = await self.ampd.playlistfind('file', filename)
        if records:
            record_id = sorted(records, key=lambda record: record['Pos'])[0]['Id']
        else:
            record_id = await self.ampd.addid(filename)
        await self.ampd.playid(record_id)

    def get_filenames(self, selection=True):
        if selection:
            store, paths = self.view.get_selection().get_selected_rows()
            rows = (store.get_record(store.get_iter(p)) for p in paths)
        else:
            rows = (self.widget.store.get_record(self.widget.store.iter_nth_child(None, i)) for i in range(self.widget.store.iter_n_children()))
        return (row.file for row in rows if row)

    def duplicate_bind_hook(self, label, item, name):
        label.get_parent().set_css_classes([])
        duplicate = item[self.duplicate_field]
        if duplicate is not None:
            label.get_parent().add_css_class(f'duplicate{duplicate % 64}')

        # status = store.get_record(i)._status
        # if status is not None:
        #     for k, p in enumerate(self.STATUS_PROPERTIES):
        #         if self.STATUS_PROPERTY_TABLE[status][k] is not None:
        #             renderer.set_property(p, self.STATUS_PROPERTY_TABLE[status][k])

    def set_records(self, records, set_fields=True):
        if set_fields:
            self.records_set_fields(records)
        if self.duplicate_test_columns:
            self.find_duplicates(records, self.duplicate_test_columns)
        self.widget.store.set_records(records)

    def records_set_fields(self, records):
        self.fields.records_set_fields(records)

    def find_duplicates(self, records, test_fields):
        dup_marker = 0
        dup_dict = {}
        for record in records:
            if record['file'] == self.unit.unit_server.SEPARATOR_FILE:
                continue
            test = tuple(record.get(field) for field in test_fields)
            duplicates = dup_dict.get(test)
            if duplicates:
                if len(duplicates) == 1:
                    duplicates[0][self.duplicate_field] = dup_marker
                    dup_marker += 1
                record[self.duplicate_field] = duplicates[0][self.duplicate_field]
                duplicates.append(record)
            else:
                dup_dict[test] = [record]
                record.pop(self.duplicate_field, None)

    def action_reset_cb(self, action, parameter):
        self.view_filter.filter_.set_data({})
        self.view_filter.active = False
        if self.sortable:
            self.widget.store.set_sort_column_id(-1, Gtk.SortType.ASCENDING)

    records_added_cb = records_removed_cb = NotImplemented


class SongListBaseWithEditDel(SongListBase):
    def __init__(self, unit, *args, **kwargs):
        super().__init__(unit, *args, **kwargs)
        self.songlistbase_actions.add_action(resource.Action('save', self.action_save_cb))
        self.songlistbase_actions.add_action(resource.Action('undelete', self.action_undelete_cb))

    def action_undelete_cb(self, action, parameter):
        store, paths = self.view.get_selection().get_selected_rows()
        for p in paths:
            i = self.widget.store.get_iter(p)
            if self.widget.store.get_record(i)._status == self.RECORD_DELETED:
                del self.widget.store.get_record(i)._status
        self.view.queue_draw()

    def record_delete_cb(self, store, i):
        if self.widget.store.get_record(i)._status == self.RECORD_UNDEFINED:
            return
        self.set_modified()
        if self.widget.store.get_record(i)._status == self.RECORD_NEW:
            self.widget.store.remove(i)
        else:
            self.widget.store.get_record(i)._status = self.RECORD_DELETED
            self.merge_new_del(i)
        self.view.queue_draw()

    def modify_record(self, i, record):
        _record = self.widget.store.get_record(i)
        status = _record._status
        if status == self.RECORD_UNDEFINED:
            return
        _record.set_data(record)
        self.set_modified()
        if status is None:
            _record._status = self.RECORD_MODIFIED
        self.view.queue_draw()

    def merge_new_del(self, i):
        _status = self.widget.store.get_record(i)._status
        for f in [self.widget.store.iter_previous, self.widget.store.iter_next]:
            j = f(i)
            if j and self.widget.store.get_record(j).file == self.widget.store.get_record(i).file and {_status, self.widget.store.get_record(j)._status} == {self.RECORD_DELETED, self.RECORD_NEW}:
                del self.widget.store.get_record(i)._status
                self.widget.store.remove(j)
                return


class SongListBaseWithAdd(SongListBase):
    def add_record(self, record):
        # dest = self.view.get_path_at_pos(int(self.view.context_menu_x), int(self.view.context_menu_y))
        # path = None if dest is None else dest[0]
        path, column = self.view.get_cursor()
        self.view.paste_at([record], path, False)


class SongListBaseWithEditDelNew(SongListBaseWithEditDel, SongListBaseWithAdd):
    def record_new_cb(self, store, i):
        self.set_modified()
        store.get_record(i)._status = self.RECORD_NEW
        self.merge_new_del(i)


class UnitMixinSongListBase(component.UnitMixinComponent):
    def __init__(self, name, manager, *, menus=[]):
        self.REQUIRED_UNITS = ['misc', 'songlistbase'] + self.REQUIRED_UNITS
        super().__init__(name, manager, menus=menus + ['context'])
