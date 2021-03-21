# coding: utf-8
#
# Graphical Asynchronous Music Player Client
#
# Copyright (C) 2015 Itaï BEN YAACOV
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

from .. import data
from . import module
from . import resource


class RecordList(module.Module):
    sortable = False
    duplicate_test_columns = []
    duplicate_field = '_duplicate'

    def __init__(self, unit):
        super().__init__(unit)
        self.treeview = data.RecordTreeView(self.fields, self.data_func, self.sortable)
        self.store = self.treeview.get_model()

        self.actions.add_action(resource.Action('reset', self.action_reset_cb))
        self.actions.add_action(resource.Action('copy', self.action_copy_delete_cb))

        if self.record_new_cb != NotImplemented:
            self.actions.add_action(resource.Action('paste', self.action_paste_cb))
            self.actions.add_action(resource.Action('paste-before', self.action_paste_cb))
            self.signal_handler_connect(self.store, 'record-new', self.record_new_cb)

        if self.record_delete_cb != NotImplemented:
            self.actions.add_action(resource.Action('delete', self.action_copy_delete_cb))
            self.actions.add_action(resource.Action('cut', self.action_copy_delete_cb))
            self.signal_handler_connect(self.store, 'record-delete', self.record_delete_cb)

        self.set_editable(True)

        self.treeview_filter = data.TreeViewFilter(self.unit.unit_misc, self.treeview)
        self.add(self.treeview_filter)
        self.actions.add_action(Gio.PropertyAction(name='filter', object=self.treeview_filter, property_name='active'))

        self.setup_context_menu('context', self.treeview)
        self.treeview.connect('row-activated', self.treeview_row_activated_cb)

        self.connect('map', self.set_color)
        self.signal_handler_connect(self.unit.unit_persistent, 'notify::dark', self.set_color)

    def set_editable(self, editable):
        dndtargets = [Gtk.TargetEntry.new(self.DND_TARGET, Gtk.TargetFlags(0), 0)]

        if self.record_new_cb != NotImplemented:
            if editable:
                self.treeview.drag_dest_set(Gtk.DestDefaults.DROP, dndtargets, Gdk.DragAction.MOVE | Gdk.DragAction.COPY)
            else:
                self.treeview.drag_dest_unset()

        if self.record_delete_cb != NotImplemented and editable:
            self.treeview.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, dndtargets, Gdk.DragAction.MOVE | Gdk.DragAction.COPY)
        else:
            self.treeview.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, dndtargets, Gdk.DragAction.COPY)

        for name in ['paste', 'paste-before', 'delete', 'cut']:
            action_ = self.actions.lookup(name)
            if action_ is not None:
                action_.set_enabled(editable)

    def set_color(self, *args):
        if self.win:
            self.color = self.win.get_style_context().get_color(Gtk.StateFlags.NORMAL)

    def action_copy_delete_cb(self, action, parameter):
        records, refs = self.treeview.get_selection_rows()
        if action.get_name() in ['copy', 'cut']:
            Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(repr(records), -1)
        if action.get_name() in ['delete', 'cut']:
            self.store.delete_refs(refs)

    def action_paste_cb(self, action, parameter):
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).request_text(self.treeview.clipboard_paste_cb, action.get_name().endswith('before'))

    @ampd.task
    async def treeview_row_activated_cb(self, treeview, p, column):
        if self.unit.unit_persistent.protected:
            return
        filename = self.store.get_record(self.store.get_iter(p)).file
        records = await self.ampd.playlistfind('file', filename)
        if records:
            record_id = sorted(records, key=lambda record: record['Pos'])[0]['Id']
        else:
            record_id = await self.ampd.addid(filename)
        await self.ampd.playid(record_id)

    def get_filenames(self, selection=True):
        if selection:
            store, paths = self.treeview.get_selection().get_selected_rows()
            rows = (store.get_record(store.get_iter(p)) for p in paths)
        else:
            rows = (self.store.get_record(self.store.iter_nth_child(None, i)) for i in range(self.store.iter_n_children()))
        return (row.file for row in rows if row)

    def _mix_colors(self, r, g, b):
        return Gdk.RGBA((1 - self.color.red) * r + 0.5 * (1 - r),
                        (1 - self.color.green) * g + 0.5 * (1 - g),
                        (1 - self.color.blue) * b + 0.5 * (1 - b),
                        1.0)

    def _mix_colors_rgba(self, rgba):
        return self._mix_colors(rgba.red, rgba.green, rgba.blue)

    def data_func(self, column, renderer, store, i, j):
        _duplicate = store.get_record(i)._data.get(self.duplicate_field, None)
        if _duplicate is None:
            renderer.set_property('background-rgba', None)
        else:
            N = 4
            m = _duplicate % (N ** 3 - 1)
            renderer.set_property('background-rgba',
                                  self._mix_colors(*(float((m // (N ** k)) % N) / (N - 1)
                                                     for k in (2, 1, 0))))

    def set_records(self, records, set_fields=True):
        if set_fields:
            self.records_set_fields(records)
        if self.duplicate_test_columns:
            self.find_duplicates(records, self.duplicate_test_columns)
        self.store.set_rows(records)

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
        self.treeview_filter.filter_.set_data({})
        self.treeview_filter.active = False
        if self.sortable:
            self.store.set_sort_column_id(-1, Gtk.SortType.ASCENDING)

    record_delete_cb = record_new_cb = NotImplemented


class RecordListWithEditDel(RecordList):
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

    def __init__(self, unit):
        super().__init__(unit)
        self.actions.add_action(resource.Action('save', self.action_save_cb))
        self.actions.add_action(resource.Action('undelete', self.action_undelete_cb))

    def data_func(self, column, renderer, store, i, j):
        for p in self.STATUS_PROPERTIES:
            renderer.set_property(p, None)
        super().data_func(column, renderer, store, i, j)
        status = store.get_record(i)._status
        if status is not None:
            for k, p in enumerate(self.STATUS_PROPERTIES):
                if self.STATUS_PROPERTY_TABLE[status][k] is not None:
                    renderer.set_property(p, self.STATUS_PROPERTY_TABLE[status][k])

    def action_undelete_cb(self, action, parameter):
        store, paths = self.treeview.get_selection().get_selected_rows()
        for p in paths:
            i = self.store.get_iter(p)
            if self.store.get_record(i)._status == self.RECORD_DELETED:
                del self.store.get_record(i)._status
        self.treeview.queue_draw()

    def record_delete_cb(self, store, i):
        if self.store.get_record(i)._status == self.RECORD_UNDEFINED:
            return
        self.set_modified()
        if self.store.get_record(i)._status == self.RECORD_NEW:
            self.store.remove(i)
        else:
            self.store.get_record(i)._status = self.RECORD_DELETED
            self.merge_new_del(i)
        self.treeview.queue_draw()

    def modify_record(self, i, record):
        _record = self.store.get_record(i)
        status = _record._status
        if status == self.RECORD_UNDEFINED:
            return
        _record.set_data(record)
        self.set_modified()
        if status is None:
            _record._status = self.RECORD_MODIFIED
        self.treeview.queue_draw()

    def merge_new_del(self, i):
        _status = self.store.get_record(i)._status
        for f in [self.store.iter_previous, self.store.iter_next]:
            j = f(i)
            if j and self.store.get_record(j).file == self.store.get_record(i).file and {_status, self.store.get_record(j)._status} == {self.RECORD_DELETED, self.RECORD_NEW}:
                del self.store.get_record(i)._status
                self.store.remove(j)
                return


class RecordListWithAdd(RecordList):
    def add_record(self, record):
        # dest = self.treeview.get_path_at_pos(int(self.treeview.context_menu_x), int(self.treeview.context_menu_y))
        # path = None if dest is None else dest[0]
        path, column = self.treeview.get_cursor()
        self.treeview.paste_at([record], path, False)


class RecordListWithEditDelNew(RecordListWithEditDel, RecordListWithAdd):
    def record_new_cb(self, store, i):
        self.set_modified()
        store.get_record(i)._status = self.RECORD_NEW
        self.merge_new_del(i)
