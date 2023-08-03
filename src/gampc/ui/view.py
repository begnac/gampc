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
from gi.repository import Gdk
from gi.repository import Gtk

import re

from ..util.record import Record

from . import column


class Store(Gio.ListStore):
    __gsignals__ = {
        'items-removed': (GObject.SIGNAL_ACTION, None, (int, int)),
        'items-added': (GObject.SIGNAL_ACTION, None, (int, int)),
    }

    def __init__(self):
        super().__init__(item_type=Record)

    def splice(self, position, n_removals, additions):
        self.emit('items-removed', position, n_removals)
        super().splice(position, n_removals, additions)
        self.emit('items-added', position, len(additions))

    def set_records(self, records):
        self[:] = map(Record, records)


class RecordView(Gtk.ColumnView):
    def __init__(self, fields, item_widget, item_bind_hooks, sortable=False, *, hide_titles=False, **kwargs):
        self.fields = fields
        self.item_widget = item_widget
        self.item_bind_hooks = item_bind_hooks
        self.sortable = sortable

        super().__init__(**kwargs)

        self.columns = self.get_columns()
        self.columns_by_name = {}
        for name in fields.order:
            name = name.get_string()
            col = column.FieldColumn(name, self.fields.fields[name], item_widget, sortable)
            col.get_factory().bound.connect('items-changed', self.bound_items_changed_cb, name)
            self.columns_by_name[name] = col
            self.append_column(col)

        if hide_titles:
            self.get_first_child().set_visible(False)
        self.columns.connect('items-changed', self.columns_changed_cb)
        self.fields.order.connect('items-changed', self.fields_order_changed_cb)

        # self.set_search_equal_func(lambda store, col, key, i: not any(isinstance(value, str) and key.lower() in value.lower() for value in store.get_record(i).get_data().values()))

    def cleanup(self):
        del self.item_widget
        self.fields.order.disconnect_by_func(self.fields_order_changed_cb)
        self.columns.disconnect_by_func(self.columns_changed_cb)
        del self.item_bind_hooks
        for col in self.columns_by_name.values():
            #############
            col.get_factory().bound = None
            col.field = None
            #############
            self.remove_column(col)
        del self.columns_by_name

    def rebind_listitem(self, listitem, name):
        item = listitem.get_item()
        child = listitem.child
        cell = child.cell
        cell.set_css_classes(cell.orig_css_classes)
        for hook in self.item_bind_hooks:
            hook(child, item, name)

    def rebind_columns(self):
        for col in self.columns_by_name.values():
            for listitem in col.get_factory().bound:
                self.rebind_listitem(listitem, col.name)

    def bound_items_changed_cb(self, bound, position, removed, added, name):
        for listitem in bound[position:position + added]:
            self.rebind_listitem(listitem, name)

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


class Entry(Gtk.Entry):
    def __init__(self, changed_cb):
        super().__init__()
        self.connect('changed', changed_cb)

    @staticmethod
    def bind(self, record, name):
        self.name = name
        self.get_buffer().set_text(record[name] or '', -1)


class View(Gtk.Box):
    filtering = GObject.Property(type=bool, default=False)

    def __init__(self, fields, sortable):
        self.bind_hooks = [self.bind_hook]
        self.sortable = sortable

        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.filter_record = Record()
        self.filter_store = Gio.ListStore(item_type=Record)
        self.filter_selection = Gtk.NoSelection(model=self.filter_store)
        self.filter_view = RecordView(fields, lambda: Entry(self.filter_entry_changed_cb), [Entry.bind], hide_titles=True, model=self.filter_selection, show_column_separators=True)
        self.filter_view.add_css_class('filter')
        self.filter_view.add_css_class('data-table')
        self.scrolled_filter_view = Gtk.ScrolledWindow(child=self.filter_view, focusable=False, vscrollbar_policy=Gtk.PolicyType.NEVER)
        self.scrolled_filter_view.get_hscrollbar().set_visible(False)
        self.append(self.scrolled_filter_view)

        self.store_selection = Gtk.MultiSelection()
        self.record_view = RecordView(fields, lambda: Gtk.Label(halign=Gtk.Align.START), self.bind_hooks, sortable, model=self.store_selection, vexpand=True, enable_rubberband=False, show_row_separators=True, show_column_separators=True)
        self.record_view.add_css_class('records')
        self.record_view.add_css_class('data-table')
        self.record_view_rows = self.record_view.get_last_child()
        self.scrolled_record_view = Gtk.ScrolledWindow(child=self.record_view, focusable=False)
        self.scrolled_record_view.get_hadjustment().bind_property('value', self.scrolled_filter_view.get_hadjustment(), 'value', GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)
        self.append(self.scrolled_record_view)

        self.store = Store()

        self.filter_filter = Gtk.CustomFilter()
        self.filter_filter.set_filter_func(self.filter_func)
        self.store_filter = Gtk.FilterListModel(model=self.store, filter=self.filter_filter)

        if sortable:
            self.store_sort = Gtk.SortListModel(model=self.store_filter, sorter=self.record_view.get_sorter())
            self.store_selection.set_model(self.store_sort)
        else:
            self.store_selection.set_model(self.store_filter)
            self.record_view.sort_by_column(None, 0)

        # self.shortcut_controller = Gtk.ShortcutController()
        # self.record_view.add_controller(self.shortcut_controller)
        # shortcut_action = Gtk.CallbackAction.new(lambda *args: print(888, args) or True)
        # shortcut_action = Gtk.NamedAction.new('songlistbase.copy')
        # shortcut = Gtk.Shortcut(action=shortcut_action, trigger=Gtk.ShortcutTrigger.parse_string('<Control>p'))
        # self.shortcut_controller.add_shortcut(shortcut)

        self.connect('notify::filtering', self.notify_filtering_cb)
        # self.connect('destroy', self.destroy_cb)

        # self.set_search_equal_func(lambda store, col, key, i: not any(isinstance(value, str) and key.lower() in value.lower() for value in store.get_record(i).get_data().values()))

        # if self.sortable:
        #     store = self.get_model()
        #     for i, name in enumerate(self.fields.order):
        #         self.columns_by_name[name].set_sort_column_id(i)
        #         store.set_sort_func(i, self.sort_func, name)

        # self.connect('drag-data-get', self.drag_data_get_cb)

    def cleanup(self):
        self.filter_filter.set_filter_func(None)
        self.filter_view.cleanup()
        self.record_view.cleanup()
        del self.bind_hooks

    @staticmethod
    def bind_hook(label, item, name):
        label.set_label(item[name] or '')

    @staticmethod
    def notify_filtering_cb(self, param):
        if self.filtering and len(self.filter_store) == 0:
            self.filter_store.append(self.filter_record)
            self.filter_filter.changed(Gtk.FilterChange.MORE_STRICT)
        if not self.filtering and len(self.filter_store) == 1:
            self.filter_store.remove(0)
            self.filter_filter.changed(Gtk.FilterChange.LESS_STRICT)

    def filter_entry_changed_cb(self, entry):
        new = entry.get_buffer().get_text()
        if not new:
            del self.filter_record[entry.name]
            self.filter_filter.changed(Gtk.FilterChange.LESS_STRICT)
        else:
            self.filter_record[entry.name] = new
            self.filter_filter.changed(Gtk.FilterChange.DIFFERENT)

    def filter_func(self, record):
        if not self.filtering:
            return True
        for name, value in self.filter_record.items():
            if re.search(value, record[name] or '', re.IGNORECASE) is None:
                return False
        return True

    # @staticmethod
    # def sort_func(store, i, j, name):
    #     try:
    #         v1 = getattr(store.get_record(i), name)
    #         v2 = getattr(store.get_record(j), name)
    #         return 0 if v1 == v2 else -1 if v1 is None or (v2 is not None and v1 < v2) else 1
    #     except AttributeError:
    #         return 0

    def _get_selection(self):
        return filter(lambda i: self.store_selection.is_selected(i), range(len(self.store_selection)))

    def get_selection(self):
        return list(self._get_selection())

    def get_selection_records(self):
        return list(map(lambda i: self.store_selection[i], self._get_selection()))

    # def clipboard_paste(self, raw, before):
    #     path, column = self.get_cursor()
    #     try:
    #         records = ast.literal_eval(raw)
    #     except Exception:
    #         return
    #     if not (isinstance(records, list) and all(isinstance(record, dict) for record in records)):
    #         return
    #     self.paste_at(records, path, before)

    # def paste_at(self, records, path, before):
    #     selection = self.get_selection()
    #     selection.unselect_all()
    #     store = self.get_model()
    #     i = store.get_iter(path) if path else None
    #     if before:
    #         i = store.iter_previous(i) if i else store.iter_nth_child(None, max(store.iter_n_children(None) - 1, 0))
    #     cursor_set = False
    #     for record in records:
    #         j = store.insert_after(i)
    #         store.set_row(j, record)
    #         ref = Gtk.TreeRowReference.new(store, store.get_path(j))
    #         store.emit('record-new', j)
    #         i = store.get_iter(ref.get_path())
    #         if not cursor_set:
    #             cursor_set = True
    #             self.set_cursor(store.get_path(i))
    #         selection.select_iter(i)
