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
from gi.repository import Gdk
from gi.repository import Gtk

import re

from .. import util

from . import listviewsearch
from . import editable


class ItemFactory(Gtk.SignalListItemFactory):
    def __init__(self, name):
        super().__init__()

        self.name = name

        self.binders = {}
        self.binders['value'] = (self.value_binder, name)
        self.binders['duplicate'] = (self.duplicate_binder,)

        self.connect('setup', self.setup_cb)
        self.connect('bind', self.bind_cb)
        self.connect('unbind', self.unbind_cb)
        # self.connect('teardown', self.teardown_cb)

    @staticmethod
    def setup_cb(self, listitem):
        listitem.set_child(self.make_widget())

    @staticmethod
    def bind_cb(self, listitem):
        widget = listitem.get_child()
        widget.pos = listitem.get_position()
        self.bind(widget, listitem.get_item())

    @staticmethod
    def unbind_cb(self, listitem):
        self.unbind(listitem.get_child(), listitem.get_item())

    # @staticmethod
    # def teardown_cb(self, listitem):
    #     pass

    def bind(self, widget, item):
        for binder, *args in self.binders.values():
            binder(widget, item, *args)
        item.connect('notify', self.notify_item_cb, widget)

    def unbind(self, widget, item):
        item.disconnect_by_func(self.notify_item_cb)

    def notify_item_cb(self, item, param, widget):
        binder, *args = self.binders[param.name]
        binder(widget, item, *args)

    @staticmethod
    def value_binder(widget, item, name):
        widget.set_label(item.get_field(name))

    @staticmethod
    def duplicate_binder(widget, item):
        if item.duplicate is None:
            suffix = None
        else:
            suffix = str(item.duplicate % 64)
        util.misc.add_unique_css_class(widget.get_parent(), 'duplicate', suffix)


class LabelItemFactory(ItemFactory):
    @staticmethod
    def make_widget():
        return Gtk.Label(halign=Gtk.Align.START)


class EditableItemFactory(ItemFactory):
    def __init__(self, name, unit_misc, always_editable=False):
        super().__init__(name)

        self.unit_misc = unit_misc
        self.always_editable = always_editable

    def make_widget(self):
        return editable.EditableLabel(always_editable=self.always_editable, unit_misc=self.unit_misc)

    def bind(self, widget, item):
        super().bind(widget, item)
        widget.connect('edited', self.label_edited_cb, item, self.name)

    def unbind(self, widget, item):
        super().unbind(widget, item)
        widget.disconnect_by_func(self.label_edited_cb)

    @staticmethod
    def label_edited_cb(widget, item, name):
        item.value[name] = widget.get_text()
        item.value = item.value


class FieldItemColumn(Gtk.ColumnViewColumn):
    def __init__(self, field, *, sortable, **kwargs):
        self.name = field.name

        super().__init__(**kwargs)

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


def clean_shortcuts(widget):
    for controller in list(widget.observe_controllers()):
        if isinstance(controller, Gtk.ShortcutController):
            new_controller = Gtk.ShortcutController()
            changed = False
            for shortcut in controller:
                trigger = shortcut.get_trigger()
                if isinstance(trigger, Gtk.KeyvalTrigger) and \
                   trigger.get_modifiers() & Gdk.ModifierType.CONTROL_MASK and \
                   trigger.get_keyval() in (Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_Left, Gdk.KEY_Right, ):
                    changed = True
                else:
                    new_controller.add_shortcut(shortcut)
            if changed:
                widget.remove_controller(controller)
                widget.add_controller(new_controller)


def clean_shortcuts_below(widget):
    clean_shortcuts(widget)
    for child in widget:
        clean_shortcuts_below(child)


class ItemView(Gtk.ColumnView):
    sortable = GObject.Property(type=bool, default=False)
    visible_titles = GObject.Property(type=bool, default=True)

    def __init__(self, fields, factory_factory, **kwargs):
        self.fields = fields
        super().__init__(show_row_separators=True, show_column_separators=True, **kwargs)
        self.add_css_class('data-table')

        self.rows = self.get_last_child()
        self.rows_model = self.rows.observe_children()
        self.rows_model.connect('items-changed', lambda model, p, r, a: [clean_shortcuts(row_widget) for row_widget in model[p:p + a]])

        self.columns = {field.name: FieldItemColumn(field, sortable=self.sortable, factory=factory_factory(field.name)) for field in fields.fields.values()}
        for name in fields.order:
            self.append_column(self.columns[name.get_string()])

        self.bind_property('visible-titles', self.get_first_child(), 'visible', GObject.BindingFlags.SYNC_CREATE)
        self.get_columns().connect('items-changed', self.columns_changed_cb)
        self.fields.order.connect('items-changed', self.fields_order_changed_cb)

    def cleanup(self):
        self.fields.order.disconnect_by_func(self.fields_order_changed_cb)
        self.get_columns().disconnect_by_func(self.columns_changed_cb)
        for col in list(self.get_columns()):
            self.remove_column(col)

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


class View(Gtk.Box):
    filtering = GObject.Property(type=bool, default=False)

    def __init__(self, fields, factory_factory, sortable, *, selection_model=Gtk.MultiSelection, unit_misc):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.unit_misc = unit_misc

        self.filter_filter = Gtk.CustomFilter()
        self.filter_filter.set_filter_func(self.filter_func)

        self.filter_item = util.item.Item(value={})
        self.filter_store = Gio.ListStore()
        self.filter_selection = Gtk.NoSelection(model=self.filter_store)
        self.filter_view = ItemView(fields, self.filter_factory_factory, sortable=False, model=self.filter_selection)
        self.filter_view.add_css_class('filter')
        self.scrolled_filter_view = Gtk.ScrolledWindow(child=self.filter_view, focusable=False, vscrollbar_policy=Gtk.PolicyType.NEVER)
        self.scrolled_filter_view.get_hscrollbar().set_visible(False)
        self.append(self.scrolled_filter_view)
        self.filter_item.connect('notify::value', self.notify_filter_cb)

        self.item_selection = selection_model()
        self.item_view = ItemView(fields, factory_factory, sortable=sortable, model=self.item_selection, vexpand=True, enable_rubberband=False)
        self.item_view.add_css_class('items')
        self.scrolled_item_view = Gtk.ScrolledWindow(child=self.item_view, focusable=False)
        self.scrolled_item_view.get_hadjustment().bind_property('value', self.scrolled_filter_view.get_hadjustment(), 'value', GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)
        self.append(self.scrolled_item_view)

        clean_shortcuts_below(self)

        self.bind_property('filtering', self.filter_view, 'visible-titles', GObject.BindingFlags.SYNC_CREATE)
        self.bind_property('filtering', self.item_view, 'visible-titles', GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.INVERT_BOOLEAN)

        self.item_store = Gio.ListStore(item_type=util.item.Item)
        # self.item_selection.set_model(self.item_store)

        self.item_store_filter = Gtk.FilterListModel(model=self.item_store)

        if sortable:
            self.item_store_sort = Gtk.SortListModel(model=self.item_store_filter, sorter=self.item_view.get_sorter())
            self.item_selection.set_model(self.item_store_sort)
        else:
            self.item_selection.set_model(self.item_store_filter)
            self.item_view.sort_by_column(None, 0)

        self.view_search = listviewsearch.ListViewSearch(self.item_view.rows, lambda text, item: any(text.lower() in item.get_field(name).lower() for name in fields.fields))

        self.connect('notify::filtering', self.notify_filtering_cb)

    def cleanup(self):
        self.filter_item.disconnect_by_func(self.notify_filter_cb)
        self.filter_filter.set_filter_func(None)
        self.filter_view.cleanup()
        self.item_store.remove_all()
        self.item_view.cleanup()
        self.view_search.cleanup()

    def filter_factory_factory(self, name):
        return EditableItemFactory(name, always_editable=True, unit_misc=self.unit_misc)

    def notify_filter_cb(self, item, param):
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
            if re.search(value, self.item_get_field(item, name), re.IGNORECASE) is None:
                return False
        return True

    def _get_selection(self):
        return util.misc.get_selection(self.item_selection)

    def get_selection(self):
        return list(self._get_selection())

    def get_selection_items(self):
        return list(map(lambda i: self.item_selection[i], self._get_selection()))

    # def get_filenames(self, selection):
    #     if selection:
    #         return list(map(lambda i: self.item_selection[i].file, self._get_selection()))
    #     else:
    #         return list(map(lambda item: item.file, self.item_selection))


class ItemViewInterface:
    def __init__(self, content_from_items, content_type=None, add_items=None, remove_items=None):
        self.content_from_items = content_from_items
        self.content_type = content_type
        self.add_items = add_items
        self.remove_items = remove_items
