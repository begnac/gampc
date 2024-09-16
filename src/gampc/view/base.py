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


from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk

import re

from ..util import cleanup
from ..util import item
from ..util import misc

from ..ui import listviewsearch

from .listitem import EditableListItemFactoryBase
from .listitem import LabelListItemFactory


class FieldItemColumn(Gtk.ColumnViewColumn):
    def __init__(self, field, *, sortable, **kwargs):
        self.name = field.name

        super().__init__(**kwargs, id=field.name)

        field.bind_property('title', self, 'title', GObject.BindingFlags.SYNC_CREATE)
        field.bind_property('visible', self, 'visible', GObject.BindingFlags.SYNC_CREATE)
        field.bind_property('width', self, 'fixed-width', GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.BIDIRECTIONAL)

        self.set_resizable(True)

        if sortable:
            sorter = Gtk.CustomSorter.new(self.sort_func, self.name)
            self.set_sorter(sorter)

    @staticmethod
    def sort_func(item1, item2, name):
        s1 = item1.get_field(name)
        s2 = item2.get_field(name)
        return Gtk.Ordering.LARGER if s1 > s2 else Gtk.Ordering.SMALLER if s1 < s2 else Gtk.Ordering.EQUAL


class ItemView(Gtk.ColumnView):
    sortable = GObject.Property(type=bool, default=False)
    visible_titles = GObject.Property(type=bool, default=True)

    def __init__(self, fields, factory_factory, **kwargs):
        self.fields = fields
        super().__init__(show_row_separators=True, show_column_separators=True, **kwargs)
        self.add_css_class('data-table')

        self.rows = self.get_last_child()
        self.rows_model = self.rows.observe_children()
        self.rows_model.connect('items-changed', lambda model, p, r, a: [misc.remove_control_move_shortcuts(row_widget) for row_widget in model[p:p + a]])

        self.columns = {field.name: FieldItemColumn(field, sortable=self.sortable, factory=factory_factory(field.name)) for field in fields.fields.values()}
        for name in fields.order:
            self.append_column(self.columns[name.get_string()])

        self.bind_property('visible-titles', self.get_first_child(), 'visible', GObject.BindingFlags.SYNC_CREATE)
        self.get_columns().connect('items-changed', self.columns_changed_cb)
        self.fields.order.connect('items-changed', self.fields_order_changed_cb)

    def cleanup(self):
        self.fields.order.disconnect_by_func(self.fields_order_changed_cb)
        self.get_columns().disconnect_by_func(self.columns_changed_cb)

    def columns_changed_cb(self, columns, position, removed, added):
        self.fields.order.handler_block_by_func(self.fields_order_changed_cb)
        self.fields.order[position:position + removed] = [Gtk.StringObject.new(col.name) for col in columns[position:position + added]]
        self.fields.order.handler_unblock_by_func(self.fields_order_changed_cb)

    def fields_order_changed_cb(self, order, position, removed, added):
        columns = self.get_columns()
        columns.handler_block_by_func(self.columns_changed_cb)
        for col in list(columns[position:position + removed]):
            self.remove_column(col)
        for i in range(position, position + added):
            self.insert_column(i, self.columns[order[i].get_string()])
        columns.handler_unblock_by_func(self.columns_changed_cb)


class ViewBase(cleanup.CleanupSignalMixin, Gtk.Box):
    filtering = GObject.Property(type=bool, default=False)

    def __init__(self, fields, *, model=None, item_type=item.Item, factory_factory=LabelListItemFactory, sortable, filterable=True, selection_model=Gtk.MultiSelection, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)

        self.sortable = sortable
        self.filterable = filterable

        next_model = self.item_model = item.ItemListStore(item_type=item_type) if model is None else model

        self.item_selection_model = selection_model()
        self.item_selection_filter_model = Gtk.SelectionFilterModel(model=self.item_selection_model)
        self.item_view = ItemView(fields, factory_factory, sortable=sortable, model=self.item_selection_model, enable_rubberband=False, hexpand=True, vexpand=True, tab_behavior=Gtk.ListTabBehavior.CELL)
        self.item_view.add_css_class('items')
        self.scrolled_item_view = Gtk.ScrolledWindow(child=self.item_view)
        self.view_search = listviewsearch.ListViewSearch(self.item_view.rows, lambda text, item: any(text.lower() in item.get_field(name).lower() for name in fields.fields))
        self.append(self.scrolled_item_view)
        self.add_cleanup_below(self.item_view, self.view_search)

        if filterable:
            self.filter_item = item.ItemBase(value={})
            self.filter_store = Gio.ListStore()
            self.filter_store_selection = Gtk.NoSelection(model=self.filter_store)
            self.filter_view = ItemView(fields, EditableListItemFactoryBase, sortable=False, model=self.filter_store_selection)
            self.filter_view.add_css_class('filter')
            self.scrolled_filter_view = Gtk.ScrolledWindow(child=self.filter_view, vscrollbar_policy=Gtk.PolicyType.NEVER)
            self.scrolled_filter_view.get_hscrollbar().set_visible(False)
            for column in self.filter_view.get_columns():
                self.connect_clean(column.get_factory(), 'item-edited', self.filter_edited_cb)
            self.prepend(self.scrolled_filter_view)
            self.add_cleanup_below(self.filter_view)

            self.bind_property('filtering', self.filter_view, 'visible-titles', GObject.BindingFlags.SYNC_CREATE)
            self.bind_property('filtering', self.item_view, 'visible-titles', GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.INVERT_BOOLEAN)
            self.scrolled_item_view.get_hadjustment().bind_property('value', self.scrolled_filter_view.get_hadjustment(), 'value', GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)
            self.connect('notify::filtering', self.notify_filtering_cb)

            self.filter_filter = Gtk.CustomFilter()
            next_model = Gtk.FilterListModel(model=next_model, filter=self.filter_filter)

            if sortable:
                next_model = Gtk.SortListModel(model=next_model, sorter=self.item_view.get_sorter())

        self.item_selection_model.set_model(next_model)

        misc.remove_control_move_shortcuts_below(self)

    def cleanup(self):
        if self.filterable:
            self.filter_filter.set_filter_func(None)
        super().cleanup()

    def grab_focus(self):
        return self.item_view.grab_focus()

    def filter_edited_cb(self, factory, pos, name, value):
        self.filter_item.value[name] = value
        self.filter_filter.changed(Gtk.FilterChange.DIFFERENT)

    @staticmethod
    def notify_filtering_cb(self, param):
        if self.filtering:
            self.filter_store.append(self.filter_item)
            self.filter_filter.set_filter_func(self.filter_func)
            self.filter_view.grab_focus()
        else:
            self.filter_store.remove(0)
            self.filter_filter.set_filter_func(None)
            self.item_view.grab_focus()

    def filter_func(self, item):
        for name, value in self.filter_item.value.items():
            if re.search(value, item.get_field(name), re.IGNORECASE) is None:
                return False
        return True

    def _get_selection(self):
        return misc.get_selection(self.item_selection_model)

    def get_selection(self):
        return list(self._get_selection())

    def get_items(self, positions):
        return list(map(lambda i: self.item_selection_model[i], positions))

    def get_filenames(self, selection):
        return list(map(lambda item: item.get_key(), self.item_selection_filter_model if selection else self.item_selection_model))

    def scroll_to(self, position):
        self.item_view.scroll_to(position, None, Gtk.ListScrollFlags.FOCUS | Gtk.ListScrollFlags.SELECT, None)
        view_height = self.item_view.rows.get_allocation().height
        # row_height = self.view.item_view.rows.get_focus_child().get_allocation().height
        self.scrolled_item_view.get_vadjustment().set_value(23 * (position + 0.5) - view_height / 2)
