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
from gi.repository import Gtk
from gi.repository import Pango

import re


def config_notify_cb(obj, param, config):
    config[param.name]._set(obj.get_property(param.name))


class Field(GObject.Object):
    title = GObject.Property(type=str)
    width = GObject.Property(type=int)
    visible = GObject.Property(type=bool, default=True)
    xalign = GObject.Property(type=float, default=0.0)

    get_value = None

    def __init__(self, name, title=None, min_width=50, get_value=None, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.title = title
        self.width = self.min_width = min_width
        if get_value:
            self.get_value = get_value

    # def get_renderer(self):
    #     return Gtk.CellRendererText(ellipsize=Pango.EllipsizeMode.END, xalign=self.xalign)

    def __repr__(self):
        return "Field '{title}'".format(title=self.title)


class FieldWithTable(Field):
    def __init__(self, name, title=None, table=None, min_width=50, **kwargs):
        super().__init__(name, title, min_width, **kwargs)
        self.table = table

    def get_value(self, record):
        for field, pattern, value in self.table:
            if not field:
                return value
            else:
                match = re.search(pattern, record.get(field, ''))
                if match:
                    return match.expand(value)


class FieldFamily(GObject.Object):
    order = GObject.Property()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.old_order = self.config.order._get(default=[])
        self.order = []
        self.config.order._set(self.order)
        self.connect('notify', config_notify_cb, self.config)

        self.names = []
        self.basic_names = []
        self.derived_names = []
        self.fields = {}

    def close(self):
        self.disconnect_by_func(config_notify_cb)

    def register_field(self, field):
        if field.name in self.names:
            raise RuntimeError("Field '{name}' already registered".format(name=field.name))
        self.names.append(field.name)
        if field.get_value:
            self.derived_names.append(field.name)
        else:
            self.basic_names.append(field.name)
        self.fields[field.name] = field

        field_config = self.config.info[field.name]
        field.connect('notify', config_notify_cb, field_config)
        field.width = field_config.width._get(default=field.width)
        field.visible = field_config.visible._get(default=field.visible)
        if field.name in self.order:
            return
        if field.name not in self.old_order:
            self.order.append(field.name)
            return
        pos = self.old_order.index(field.name)
        for i, name in enumerate(self.order):
            if name not in self.old_order or self.old_order.index(name) > pos:
                self.order.insert(i, field.name)
                return
        else:
            self.order.append(field.name)

    def unregister_field(self, field):
        self.names.remove(field.name)
        if field.name in self.basic_names:
            self.basic_names.remove(field.name)
        else:
            self.derived_names.remove(field.name)
        del self.fields[field.name]
        field.disconnect_by_func(config_notify_cb)

    def record_set_fields(self, record):
        for name in self.derived_names:
            value = self.fields[name].get_value(record)
            if value is not None:
                record[name] = value

    def records_set_fields(self, records):
        for record in records:
            self.record_set_fields(record)


class FieldColumnFactory(Gtk.SignalListItemFactory):
    bound = GObject.Property(type=Gio.ListStore)

    def __init__(self, factory):
        super().__init__(bound=Gio.ListStore())

        self.factory = factory

        self.connect('setup', self.setup_cb)
        self.connect('bind', self.bind_cb)
        self.connect('unbind', self.unbind_cb)
        # self.connect('teardown', self.teardown_cb)

    @staticmethod
    def setup_cb(self, listitem):
        # label = Gtk.Label(halign=Gtk.Align.START, hexpand=True, vexpand=True)
        listitem.child = self.factory()
        listitem.set_child(listitem.child)

    @staticmethod
    def bind_cb(self, listitem):
        listitem.cell = listitem.child.get_parent()
        listitem.cell_css_classes = listitem.cell.get_css_classes()
        self.bound.append(listitem)

    @staticmethod
    def unbind_cb(self, listitem):
        found, position = self.bound.find(listitem)
        self.bound.remove(position)

    # @staticmethod
    # def teardown_cb(self, listitem):
    #     self.labels.remove(listitem.label)


class FieldColumn(Gtk.ColumnViewColumn):
    # width_rw = GObject.Property(type=int)

    def __init__(self, name, field, bind_hook):
        self.name = name
        self.field = field
        self.bind_hook = bind_hook

        self.factory = FieldColumnFactory(lambda: Gtk.Label(halign=Gtk.Align.START, hexpand=True, vexpand=True))
        super().__init__(id=field.name, factory=self.factory)
        field.bind_property('title', self, 'title', GObject.BindingFlags.SYNC_CREATE)
        field.bind_property('visible', self, 'visible', GObject.BindingFlags.SYNC_CREATE)

        self.factory.bound.connect('items-changed', self.bound_items_changed_cb)

        # self.set_min_width(field.min_width)
        # self.connect('notify::width-rw', self.notify_width_rw_cb)
        # field.bind_property('width', self, 'width-rw', GObject.BindingFlags.SYNC_CREATE)
        # self.bind_property('width', field, 'width')
        # self.set_resizable(True)
        # self.set_reorderable(True)
        # self.pack_start(self.renderer, True)
        # self.set_cell_data_func(self.renderer, self.data_func)

    # @staticmethod
    # def notify_width_rw_cb(self, detail):
    #     if self.width_rw != self.get_width():
    #         self.set_fixed_width(self.width_rw)

    def rebind_listitem(self, listitem):
        item = listitem.get_item()
        listitem.child.set_label(item[self.name] or '')
        listitem.cell.set_css_classes(listitem.cell_css_classes)
        self.bind_hook(listitem.child, item, self.name)

    def rebind_all(self):
        for listitem in self.factory.bound:
            self.rebind_listitem(listitem)

    def bound_items_changed_cb(self, bound, position, removed, added):
        for i in range(added):
            self.rebind_listitem(bound[position + i])
