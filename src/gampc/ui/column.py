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


class FieldItemFactory(Gtk.SignalListItemFactory):
    def __init__(self, name, widget_factory):
        super().__init__()

        self.name = name
        self.widget_factory = widget_factory

        self.connect('setup', self.setup_cb)
        self.connect('bind', self.bind_cb)
        self.connect('unbind', self.unbind_cb)
        # self.connect('teardown', self.teardown_cb)

    @staticmethod
    def setup_cb(self, listitem):
        listitem.child = self.widget_factory()
        listitem.set_child(listitem.child)

    @staticmethod
    def bind_cb(self, listitem):
        child = listitem.child
        cell = child.get_parent()
        cell._pos = listitem.get_position()
        listitem.get_item().bind(child, self.name)

    @staticmethod
    def unbind_cb(self, listitem):
        listitem.get_item().unbind(self.name)

    # @staticmethod
    # def teardown_cb(self, listitem):
    #     pass


class FieldItemColumn(Gtk.ColumnViewColumn):
    def __init__(self, name, field, widget_factory, *, sortable):
        self.name = name

        super().__init__(factory=FieldItemFactory(name, widget_factory))

        field.bind_property('title', self, 'title', GObject.BindingFlags.SYNC_CREATE)
        field.bind_property('visible', self, 'visible', GObject.BindingFlags.SYNC_CREATE)
        field.bind_property('width', self, 'fixed-width', GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.BIDIRECTIONAL)

        self.set_resizable(True)

        if sortable:
            sorter = Gtk.CustomSorter.new(self.sort_func, name)
            self.set_sorter(sorter)

    @staticmethod
    def sort_func(item1, item2, name):
        s1 = item1.get_data_now.get(name, '')
        s2 = item2.get_data_now.get(name, '')
        return Gtk.Ordering.LARGER if s1 > s2 else Gtk.Ordering.SMALLER if s1 < s2 else Gtk.Ordering.EQUAL


class FieldColumnFactory(Gtk.SignalListItemFactory):
    def __init__(self, widget_factory):
        super().__init__()

        self.connect('setup', self.setup_cb, widget_factory)
        self.connect('bind', self.bind_cb)
        self.connect('unbind', self.unbind_cb)
        # self.connect('teardown', self.teardown_cb)

    @staticmethod
    def setup_cb(self, listitem, widget_factory):
        listitem.child = widget_factory()
        listitem.set_child(listitem.child)

    @staticmethod
    def bind_cb(self, listitem):
        child = listitem.child
        cell = child.get_parent()
        cell._pos = listitem.get_position()
        child.bind(listitem.get_item())

    @staticmethod
    def unbind_cb(self, listitem):
        listitem.child.unbind()

    # @staticmethod
    # def teardown_cb(self, listitem):
    #     pass


class ColumnDef(GObject.Object):
    name = GObject.Property(type=str)
    title = GObject.Property(type=str)
    visible = GObject.Property(type=bool, default=True)
    fixed_width = GObject.Property(type=int)
    editable = GObject.Property(type=bool, default=False)


# class ColumnWithDefinition(Gtk.ColumnViewColumn):
#     def __init__(self, definition, **kwargs):
#         self.definition = definition
#         super().__init__(title=definition.title, visible=definition.visible, resizable=True, **kwargs)
#         definition.bind_property('fixed-width', self, 'fixed-width', GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.BIDIRECTIONAL)

#         if sortable:
#             sorter = Gtk.CustomSorter.new(self.sort_func, name)
#             self.set_sorter(sorter)

#     @staticmethod
#     def sort_func(record1, record2, name):
#         s1 = record1[name] or ''
#         s2 = record2[name] or ''
#         return Gtk.Ordering.LARGER if s1 > s2 else Gtk.Ordering.SMALLER if s1 < s2 else Gtk.Ordering.EQUAL


# class AutoColumnView(Gtk.ColumnView):
#     sortable = GObject.Property(type=bool, default=False)
#     editable = GObject.Property(type=bool, default=True)
#     visible_titles = GObject.Property(type=bool, default=True)
#     column_defs = GObject.Property(type=Gio.ListModel)

#     __gsignals__ = {
#         'record-changed': (GObject.SIGNAL_RUN_FIRST, None, (GObject.Object, str, str)),
#     }

#     def __init__(self, column_defs, item_bind_hooks, *, unit_misc, **kwargs):
#         super().__init__(**kwargs)
#         self.bind_property('visible-titles', self.get_first_child(), 'visible', GObject.BindingFlags.SYNC_CREATE)

#         self.columns_by_name = {}
#         for column_def in self.column_defs:
#             name = column_def.name
#             factory = self.get_wiget_factory(column_def.editable)
#             factory.bound.connect('items-changed', self.bound_items_changed_cb, name)
#             column = Gtk.ColumnViewColumn(title=column_def.title, visible=column_def.visible, resizable=True, factory=factory)
#             self.columns_by_name[name] = column
#             self.append_column(column)

#         self.get_columns().connect('items-changed', self.columns_changed_cb)
#         self.column_definitions.connect('items-changed', self.column_definitions_changed_cb)

#     def cleanup(self):
#         # self.fields.order.disconnect_by_func(self.fields_order_changed_cb)
#         # self.columns.disconnect_by_func(self.columns_changed_cb)
#         # del self.item_bind_hooks
#         for column in self.get_columns():
#             column.set_factory(None)
#         # del self.columns_by_name

#     def columns_changed_cb(self, columns, position, removed, added):
#         self.column_definitions.handler_block_by_func(self.column_definitions_changed_cb)
#         self.column_definitions[position:position + removed] = [column.definition for column in columns[position:position + added]]
#         self.column_definitions.handler_unblock_by_func(self.column_definitions_changed_cb)

#     def column_definitions_changed_cb(self, definitions, position, removed, added):
#         self.get_columns().handler_block_by_func(self.columns_changed_cb)
#         for column in list(self.get_columns()[position:position + removed]):
#             self.remove_column(column)
#         for i in range(position, position + added):
#             self.insert_column(i, self.columns_by_name[definitions[i].name])
#         self.get_columns().handler_unblock_by_func(self.columns_changed_cb)


# class AutoColumnViewAllEditable(AutoColumnView):
#     def get_widget_factory(self, editable):
#         return super().get_widget_factory(True)


class FieldColumn(Gtk.ColumnViewColumn):
    def __init__(self, name, field, widget_factory, *, sortable):
        self.name = name

        super().__init__(factory=FieldColumnFactory(widget_factory))

        field.bind_property('title', self, 'title', GObject.BindingFlags.SYNC_CREATE)
        field.bind_property('visible', self, 'visible', GObject.BindingFlags.SYNC_CREATE)
        field.bind_property('width', self, 'fixed-width', GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.BIDIRECTIONAL)

        self.set_resizable(True)

        if sortable:
            sorter = Gtk.CustomSorter.new(self.sort_func, name)
            self.set_sorter(sorter)

    @staticmethod
    def sort_func(record1, record2, name):
        s1 = record1[name] or ''
        s2 = record2[name] or ''
        return Gtk.Ordering.LARGER if s1 > s2 else Gtk.Ordering.SMALLER if s1 < s2 else Gtk.Ordering.EQUAL
