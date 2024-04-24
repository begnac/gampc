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


def config_notify_cb(obj, param, config):
    config[param.name]._set(obj.get_property(param.name))


class Field(GObject.Object):
    title = GObject.Property(type=str)
    width = GObject.Property(type=int)
    visible = GObject.Property(type=bool, default=True)
    xalign = GObject.Property(type=float, default=0.0)
    editable = GObject.Property(type=bool, default=False)

    get_value = None

    def __init__(self, name, title=None, min_width=50, get_value=None, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.title = title
        self.width = self.min_width = min_width
        if get_value:
            self.get_value = get_value

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
    order = GObject.Property(type=Gio.ListStore)

    def __init__(self, config):
        super().__init__(order=Gio.ListStore(item_type=Gtk.StringObject))
        self.config = config
        self.old_order = self.config.order._get(default=[])
        self.config.order._set([])
        self.order.connect('items-changed', self.order_changed_cb, self.config)

        self.names = []
        self.basic_names = []
        self.derived_names = []
        self.fields = {}

    @staticmethod
    def order_changed_cb(order, position, removed, added, config):
        config.order._set([name.get_string() for name in order])

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
        if field.name in list(self.order):
            return
        if field.name not in self.old_order:
            self.order.append(Gtk.StringObject.new(field.name))
            return
        pos = self.old_order.index(field.name)
        for i, name in enumerate(self.order):
            if name.get_string() not in self.old_order or self.old_order.index(name.get_string()) > pos:
                self.order.insert(i, Gtk.StringObject.new(field.name))
                return
        else:
            self.order.append(Gtk.StringObject.new(field.name))

    def unregister_field(self, field):
        self.names.remove(field.name)
        if field.name in self.basic_names:
            self.basic_names.remove(field.name)
        else:
            self.derived_names.remove(field.name)
        del self.fields[field.name]
        field.disconnect_by_func(config_notify_cb)

    def set_derived_fields(self, record):
        for name in self.derived_names:
            value = self.fields[name].get_value(record)
            if value is not None:
                record[name] = value