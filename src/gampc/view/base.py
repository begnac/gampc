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


import re
import functools

from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk

from ..util import cleanup
from ..util import item
from ..util import misc

from ..ui import editable
from ..ui import listviewsearch


class FieldItemColumn(Gtk.ColumnViewColumn):
    def __init__(self, field, *, sortable, **kwargs):
        super().__init__(**kwargs, id=field.name, title=field.title)

        field.bind_property('width', self, 'fixed-width', GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.BIDIRECTIONAL)

        self.set_resizable(True)

        if sortable:
            sorter = Gtk.CustomSorter.new(self.sort_func, field)
            self.set_sorter(sorter)

    @staticmethod
    def sort_func(item1, item2, field):
        s1 = item1.get_field(field.name, field.sort_default)
        s2 = item2.get_field(field.name, field.sort_default)
        return Gtk.Ordering.LARGER if s1 > s2 else Gtk.Ordering.SMALLER if s1 < s2 else Gtk.Ordering.EQUAL


class ItemView(Gtk.ColumnView):
    sortable = GObject.Property(type=bool, default=False)
    visible_titles = GObject.Property(type=bool, default=True)

    def __init__(self, fields, factory_factory, widget_factory, **kwargs):
        super().__init__(show_row_separators=True, show_column_separators=True, **kwargs)
        self.add_css_class('data-table')

        self.fields = fields
        self.columns = {field.name: FieldItemColumn(field, sortable=self.sortable, factory=factory_factory(field.name, widget_factory)) for field in fields.infos.values()}
        for name in fields.order:
            self.append_column(self.columns[name])
        self.rows = self.get_last_child()

        self.bind_property('visible-titles', self.get_first_child(), 'visible', GObject.BindingFlags.SYNC_CREATE)
        self.get_columns().connect('items-changed', self.columns_changed_cb)
        self.fields.connect('notify::order', self.fields_notify_order_cb, self.get_columns())

    def cleanup(self):
        self.fields.disconnect_by_func(self.fields_notify_order_cb)
        self.get_columns().disconnect_by_func(self.columns_changed_cb)

    def columns_changed_cb(self, columns, position, removed, added):
        self.fields.handler_block_by_func(self.fields_notify_order_cb)
        self.fields.order[:] = [col.get_id() for col in columns]
        self.fields.notify('order')
        self.fields.handler_unblock_by_func(self.fields_notify_order_cb)

    def fields_notify_order_cb(self, fields, param, columns):
        columns.handler_block_by_func(self.columns_changed_cb)
        for i, name in enumerate(fields.order):
            self.insert_column(i, self.columns[name])
        columns.handler_unblock_by_func(self.columns_changed_cb)


class ViewBase(cleanup.CleanupSignalMixin, Gtk.Box):
    filtering = GObject.Property(type=bool, default=False)

    def __init__(self, fields, *, model=None, item_type=item.SongItem, factory_factory=item.ListItemFactory, widget_factory=functools.partial(Gtk.Label, halign=Gtk.Align.START), sortable, filterable=True, selection_model=Gtk.MultiSelection, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)

        self.sortable = sortable
        self.filterable = filterable

        next_model = self.item_model = item.ItemListStore(item_type=item_type) if model is None else model

        self.item_selection_model = selection_model()
        self.item_selection_filter_model = Gtk.SelectionFilterModel(model=self.item_selection_model)
        self.item_view = ItemView(fields, factory_factory, widget_factory, sortable=sortable, model=self.item_selection_model, enable_rubberband=False, hexpand=True, vexpand=True, tab_behavior=Gtk.ListTabBehavior.CELL)
        self.item_view.add_css_class('items')
        self.scrolled_item_view = Gtk.ScrolledWindow(child=self.item_view)
        self.view_search = listviewsearch.ListViewSearch(self.item_view.rows, self.search_func, list(fields.infos))
        self.append(self.scrolled_item_view)
        self.add_cleanup_below(self.item_view, self.view_search)

        if filterable:
            self.filter_manager = editable.EditManager()
            self.connect_clean(self.filter_manager, 'edited', self.filter_edited_cb)
            self.filter_item = item.Item(value={})
            self.filter_store = Gio.ListStore()
            self.filter_store_selection = Gtk.NoSelection(model=self.filter_store)
            self.filter_view = ItemView(fields, item.ListItemFactory, functools.partial(editable.EditableLabel, self.filter_manager), sortable=False, model=self.filter_store_selection)
            self.filter_view.add_css_class('filter')
            self.scrolled_filter_view = Gtk.ScrolledWindow(child=self.filter_view, vscrollbar_policy=Gtk.PolicyType.NEVER)
            self.scrolled_filter_view.get_hscrollbar().set_visible(False)
            self.add_cleanup_below(self.filter_view)

            self.scrolled_item_view.get_hadjustment().bind_property('value', self.scrolled_filter_view.get_hadjustment(), 'value', GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)
            self.connect('notify::filtering', self.__class__.notify_filtering_cb)

            self.filter_filter = Gtk.CustomFilter()
            next_model = Gtk.FilterListModel(model=next_model, filter=self.filter_filter)

            if sortable:
                next_model = Gtk.SortListModel(model=next_model, sorter=self.item_view.get_sorter())

        self.item_selection_model.set_model(next_model)

    @staticmethod
    def search_func(text, item, fields):
        return any(text.lower() in str(item.get_field(name, '')).lower() for name in fields)

    def grab_focus(self):
        return self.item_view.grab_focus()

    def filter_edited_cb(self, manager, widget, changes):
        self.filter_item.value.update(changes)
        self.filter_filter.changed(Gtk.FilterChange.DIFFERENT)

    def notify_filtering_cb(self, param):
        if self.filtering:
            self.item_view.visible_titles = False
            self.prepend(self.scrolled_filter_view)
            self.filter_store.append(self.filter_item)
            self.filter_filter.set_filter_func(self.filter_func, self.filter_item)
            self.filter_view.grab_focus()
        else:
            self.remove(self.scrolled_filter_view)
            self.item_view.visible_titles = True
            self.filter_store.remove(0)
            self.filter_filter.set_filter_func(None)
            self.item_view.grab_focus()

    @staticmethod
    def filter_func(item, filter_item):
        for name, pattern in filter_item.value.items():
            value = item.get_field(name)
            if value is None or re.search(pattern, value, re.IGNORECASE) is None:
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
        row = self.item_view.rows.get_first_child()
        if row is None:
            return
        view_height = self.item_view.rows.get_allocation().height
        row_height = row.get_allocation().height
        self.scrolled_item_view.get_vadjustment().set_value(row_height * (position + 0.5) - view_height / 2)
        self.item_view.scroll_to(position, None, Gtk.ListScrollFlags.FOCUS | Gtk.ListScrollFlags.SELECT, None)
