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

import re

from .. import util

from . import column
from . import listviewsearch
from . import editable


class ItemView(Gtk.ColumnView):
    sortable = GObject.Property(type=bool, default=False)
    visible_titles = GObject.Property(type=bool, default=True)
    # column_defs = GObject.Property(type=Gio.ListModel)

    def __init__(self, fields, widget_factory, **kwargs):
        self.fields = fields

        super().__init__(**kwargs)

        self.columns = self.get_columns()
        self.columns_by_name = {}
        for name in fields.order:
            name = name.get_string()
            field = self.fields.fields[name]
            col = column.FieldItemColumn(name, field, widget_factory, sortable=self.sortable)
            self.columns_by_name[name] = col
            self.append_column(col)

        self.bind_property('visible-titles', self.get_first_child(), 'visible', GObject.BindingFlags.SYNC_CREATE)
        self.columns.connect('items-changed', self.columns_changed_cb)
        self.fields.order.connect('items-changed', self.fields_order_changed_cb)

    def cleanup(self):
        self.fields.order.disconnect_by_func(self.fields_order_changed_cb)
        self.columns.disconnect_by_func(self.columns_changed_cb)
        for col in self.columns_by_name.values():
            col.set_factory(None)
        del self.columns_by_name

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

    def __init__(self, fields, widget_factory, item_store, sortable, *, selection_model=Gtk.MultiSelection, unit_misc):
        # self.sortable = sortable

        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.filter_filter = Gtk.CustomFilter()
        self.filter_filter.set_filter_func(self.filter_func)

        self.filter_item = util.item.ItemWithDict(value={})
        self.filter_store = util.item.ItemListStore(item_factory=None)
        self.filter_selection = Gtk.NoSelection(model=self.filter_store)
        self.filter_view = ItemView(fields, lambda: editable.EditableLabel(unit_misc=unit_misc), sortable=False, model=self.filter_selection, show_column_separators=True)
        self.filter_view.add_css_class('filter')
        self.filter_view.add_css_class('data-table')
        self.scrolled_filter_view = Gtk.ScrolledWindow(child=self.filter_view, focusable=False, vscrollbar_policy=Gtk.PolicyType.NEVER)
        self.scrolled_filter_view.get_hscrollbar().set_visible(False)
        self.append(self.scrolled_filter_view)
        self.filter_item.connect('changed', self.filter_changed_cb)

        self.item_selection = selection_model()
        self.item_view = ItemView(fields, widget_factory, sortable=sortable, model=self.item_selection, vexpand=True, enable_rubberband=False, show_row_separators=True, show_column_separators=True, visible_titles=False)
        self.item_view.add_css_class('items')
        self.item_view.add_css_class('data-table')
        self.item_view_rows = self.item_view.get_last_child()
        self.scrolled_item_view = Gtk.ScrolledWindow(child=self.item_view, focusable=False)
        self.scrolled_item_view.get_hadjustment().bind_property('value', self.scrolled_filter_view.get_hadjustment(), 'value', GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)
        self.append(self.scrolled_item_view)

        self.item_store = item_store
        # self.item_selection.set_model(self.item_store)

        self.item_store_filter = Gtk.FilterListModel(model=self.item_store)

        if sortable:
            self.item_store_sort = Gtk.SortListModel(model=self.item_store_filter, sorter=self.item_view.get_sorter())
            self.item_selection.set_model(self.item_store_sort)
        else:
            self.item_selection.set_model(self.item_store_filter)
            self.item_view.sort_by_column(None, 0)

        self.view_search = listviewsearch.ListViewSearch()
        self.view_search.setup(self.item_view_rows, lambda text, item: any(text.lower() in value.lower() for value in item.get_data_clean().values()))

        self.connect('notify::filtering', self.notify_filtering_cb)

    def cleanup(self):
        self.filter_item.disconnect_by_func(self.filter_changed_cb)
        self.filter_filter.set_filter_func(None)
        self.filter_view.cleanup()
        self.item_view.cleanup()
        self.view_search.cleanup()

    # @staticmethod
    # def item_bind_hook(widget, item):
    #     value = item[widget.name]
    #     widget.props.label = '' if value is None else str(value)
    #     widget.get_parent().set_css_classes([])

    def filter_changed_cb(self, item):
        # if not value:
        #     del item[key]
        #     self.filter_filter.changed(Gtk.FilterChange.LESS_STRICT)
        # else:
        #     item[key] = value
        self.filter_filter.changed(Gtk.FilterChange.DIFFERENT)

    @staticmethod
    def notify_filtering_cb(self, param):
        if self.filtering:
            self.filter_store.append(self.filter_item)
            self.item_store_filter.set_filter(self.filter_filter)
        else:
            self.filter_store.remove(0)
            self.item_store_filter.set_filter(None)

    def filter_func(self, item):
        for name, value in self.filter_item.value.items():
            if re.search(value, item.get_data_now().get(name, ''), re.IGNORECASE) is None:
                return False
        return True

    def get_current_position(self):
        if (row := self.item_view_rows.get_focus_child()) is not None:
            return row.get_first_child()._pos
        found, i, pos = Gtk.BitsetIter.init_first(self.item_selection.get_selection())
        if found and not i.next()[0]:
            return pos
        else:
            return None

    def _get_selection(self):
        return util.misc.get_selection(self.item_selection)

    def get_selection(self):
        return list(self._get_selection())

    def get_selection_items(self):
        return list(map(lambda i: self.item_selection[i], self._get_selection()))

    def get_filenames(self, selection):
        if selection:
            return list(map(lambda i: self.item_selection[i].file, self._get_selection()))
        else:
            return list(map(lambda item: item.file, self.item_selection))
