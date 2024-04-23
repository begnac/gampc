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
from gi.repository import Gio
from gi.repository import Gtk

import re

from .. import util

from . import column
from . import listviewsearch
from . import misc


class RecordItemWidget:
    def __init__(self, name, record_changed_cb, record_edited_cb, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.record_changed_cb = record_changed_cb
        self.record_edited_cb = record_edited_cb

    def bind(self, record):
        self.record = record
        self.record_changed_cb(record, self)
        record.connect('changed', self.record_changed_cb, self)

    def unbind(self):
        self.record.disconnect_by_func(self.record_changed_cb)
        del self.record


class RecordItemLabel(RecordItemWidget, Gtk.Label):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, halign=Gtk.Align.START, **kwargs)


class RecordItemEditableLabel(RecordItemWidget, misc.EditableLabel):
    def do_edited(self):
        self.record_edited_cb(self.record, self.name, self.get_text())


class RecordView(Gtk.ColumnView):
    sortable = GObject.Property(type=bool, default=False)
    editable = GObject.Property(type=bool, default=True)
    visible_titles = GObject.Property(type=bool, default=True)
    # column_defs = GObject.Property(type=Gio.ListModel)

    __gsignals__ = {
        'record-changed': (GObject.SIGNAL_RUN_FIRST, None, (GObject.Object, str, str)),
    }

    def __init__(self, fields, record_changed_hooks, record_edited_hooks, unit_misc, *, force_editable=False, **kwargs):
        self.fields = fields
        self.record_changed_hooks = record_changed_hooks
        self.record_edited_hooks = record_edited_hooks

        super().__init__(**kwargs)

        self.columns = self.get_columns()
        self.columns_by_name = {}
        for name in fields.order:
            name = name.get_string()
            field = self.fields.fields[name]
            col = column.FieldColumn(name, field, self.get_widget_factory(name, force_editable or field.editable, unit_misc), sortable=self.sortable)
            self.columns_by_name[name] = col
            self.append_column(col)

        self.bind_property('visible-titles', self.get_first_child(), 'visible', GObject.BindingFlags.SYNC_CREATE)
        self.columns.connect('items-changed', self.columns_changed_cb)
        self.fields.order.connect('items-changed', self.fields_order_changed_cb)

    def cleanup(self):
        self.fields.order.disconnect_by_func(self.fields_order_changed_cb)
        self.columns.disconnect_by_func(self.columns_changed_cb)
        del self.record_changed_hooks
        for col in self.columns_by_name.values():
            col.set_factory(None)
        del self.columns_by_name

    def get_widget_factory(self, name, editable, unit_misc):
        if editable:
            return lambda: RecordItemEditableLabel(name, self.record_changed_cb, self.record_edited_cb, unit_misc=unit_misc)
        else:
            return lambda: RecordItemLabel(name, self.record_changed_cb, None)

    def record_changed_cb(self, record, widget):
        for hook in self.record_changed_hooks:
            hook(widget, record)

    def record_edited_cb(self, record, name, value):
        for hook in self.record_edited_hooks:
            hook(record, name, value)

    def columns_changed_cb(self, columns, position, removed, added):
        self.fields.order.handler_block_by_func(self.fields_order_changed_cb)
        self.fields.order[position:position + removed] = [Gtk.StringObject.new(col.name) for col in columns[position:position + added]]
        self.fields.order.handler_unblock_by_func(self.fields_order_changed_cb)

    def fields_order_changed_cb(self, order, position, removed, added):
        self.columns.handler_block_by_func(self.columns_changed_cb)
        for col in list(self.columns[position:position + removed]):
            self.remove_column(col)
        for i in range(position, position + added):
            self.insert_column(i, self.columns_by_name[order[i].get_string()])
        self.columns.handler_unblock_by_func(self.columns_changed_cb)


class View(Gtk.Box):
    filtering = GObject.Property(type=bool, default=False)

    def __init__(self, fields, sortable, unit_misc, *, selection_model=Gtk.MultiSelection):
        self.record_changed_hooks = [self.record_changed_hook]
        self.record_edited_hooks = []
        # self.sortable = sortable
        self.unit_misc = unit_misc

        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.filter_filter = Gtk.CustomFilter()
        self.filter_filter.set_filter_func(self.filter_func)

        self.filter_record = util.record.Record()
        self.filter_store = Gio.ListStore(item_type=util.record.Record)
        self.filter_store.append(self.filter_record)
        self.filter_selection = Gtk.NoSelection(model=self.filter_store)
        self.filter_view = RecordView(fields, [self.filter_entry_bind], [], self.unit_misc, model=self.filter_selection, show_column_separators=True, visible=False)
        self.filter_view.add_css_class('filter')
        self.filter_view.add_css_class('data-table')
        self.scrolled_filter_view = Gtk.ScrolledWindow(child=self.filter_view, focusable=False, vscrollbar_policy=Gtk.PolicyType.NEVER)
        self.scrolled_filter_view.get_hscrollbar().set_visible(False)
        self.append(self.scrolled_filter_view)

        self.record_selection = selection_model()
        self.record_view = RecordView(fields, self.record_changed_hooks, self.record_edited_hooks, self.unit_misc, sortable=sortable, model=self.record_selection, vexpand=True, enable_rubberband=False, show_row_separators=True, show_column_separators=True)
        self.record_view.add_css_class('records')
        self.record_view.add_css_class('data-table')
        self.record_view_rows = self.record_view.get_last_child()
        self.scrolled_record_view = Gtk.ScrolledWindow(child=self.record_view, focusable=False)
        self.scrolled_record_view.get_hadjustment().bind_property('value', self.scrolled_filter_view.get_hadjustment(), 'value', GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)
        self.append(self.scrolled_record_view)

        self.record_store = Gio.ListStore(item_type=util.record.Record)

        self.record_store_filter = Gtk.FilterListModel(model=self.record_store)

        if sortable:
            self.record_store_sort = Gtk.SortListModel(model=self.record_store_filter, sorter=self.record_view.get_sorter())
            self.record_selection.set_model(self.record_store_sort)
        else:
            self.record_selection.set_model(self.record_store_filter)
            self.record_view.sort_by_column(None, 0)

        self.view_search = listviewsearch.ListViewSearch()
        self.view_search.setup(self.record_view_rows, lambda text, record: any(text.lower() in value.lower() for value in record.get_data_clean().values()))

        self.connect('notify::filtering', self.notify_filtering_cb)

    def cleanup(self):
        self.filter_filter.set_filter_func(None)
        self.filter_view.cleanup()
        self.record_view.cleanup()
        del self.record_changed_hooks
        self.view_search.cleanup()

    def make_filter_entry(self):
        filter_entry = misc.Entry(unit_misc=self.unit_misc)
        filter_entry.connect('changed', self.filter_entry_changed_cb, self.filter_record, self.filter_filter)
        return filter_entry

    @staticmethod
    def filter_entry_bind(entry, record_, name):
        entry.name = name
        entry.get_buffer().set_text(record_[name] or '', -1)

    @staticmethod
    def filter_entry_changed_cb(entry, record, filter_):
        new = entry.get_buffer().get_text()
        if not new:
            del record[entry.name]
            filter_.changed(Gtk.FilterChange.LESS_STRICT)
        else:
            record[entry.name] = new
            filter_.changed(Gtk.FilterChange.DIFFERENT)

    @staticmethod
    def record_changed_hook(widget, record):
        value = record[widget.name]
        widget.props.label = '' if value is None else str(value)
        widget.get_parent().set_css_classes([])

    @staticmethod
    def notify_filtering_cb(self, param):
        self.filter_view.set_visible(self.filtering)
        if self.filtering:
            self.record_store_filter.set_filter(self.filter_filter)
        else:
            self.record_store_filter.set_filter(None)

    def filter_func(self, record):
        for name, value in self.filter_record.items():
            if re.search(value, record[name] or '', re.IGNORECASE) is None:
                return False
        return True

    def get_current_position(self):
        if (row := self.record_view_rows.get_focus_child()) is not None:
            return row.get_first_child()._pos
        found, i, pos = Gtk.BitsetIter.init_first(self.record_selection.get_selection())
        if found and not i.next()[0]:
            return pos
        else:
            return None

    def _get_selection(self):
        return util.misc.get_selection(self.record_selection)

    def get_selection(self):
        return list(self._get_selection())

    def get_selection_records(self):
        return list(map(lambda i: self.record_selection[i], self._get_selection()))

    def get_filenames(self, selection):
        if selection:
            return list(map(lambda i: self.record_selection[i].file, self._get_selection()))
        else:
            return list(map(lambda record: record.file, self.record_selection))
