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

from gi.repository import GObject
from gi.repository import Gio
from gi.repository import Gtk

from . import config


def get_fields_config():
    return config.ConfigFixedDict({
        'info': config.ConfigOpenDict(config.ConfigFixedDict({
            'visible': config.ConfigItem(bool),
            'width': config.ConfigItem(int),
        })),
        'order': config.ConfigList(config.ConfigItem(str)),
    })


def config_notify_cb(obj, param, config):
    config[param.name] = obj.get_property(param.name)


class Field(GObject.Object):
    title = GObject.Property(type=str)
    width = GObject.Property(type=int)
    visible = GObject.Property(type=bool, default=True)
    editable = GObject.Property(type=bool, default=False)

    get_value = None

    def __init__(self, name, title=None, *, sort_default='', min_width=50, get_value=None, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.title = title
        self.sort_default = sort_default
        self.width = self.min_width = min_width
        if get_value:
            self.get_value = get_value

    def __repr__(self):
        return "Field '{title}'".format(title=self.title)


class FieldWithTable(Field):
    def __init__(self, name, title=None, table=None, **kwargs):
        super().__init__(name, title, **kwargs)
        self.table = table

    def get_value(self, data):
        for field, pattern, value in self.table:
            if not field:
                return value
            else:
                match = re.search(pattern, data.get(field, ''))
                if match:
                    return match.expand(value)


class FieldFamily(GObject.Object):
    order = GObject.Property(type=Gio.ListStore)

    def __init__(self, config):
        super().__init__(order=Gio.ListStore(item_type=Gtk.StringObject))
        self.config = config
        self.old_order, self.config['order'] = self.config['order'], []
        self.order.connect('items-changed', self.order_changed_cb, self.config)

        self.names = []
        self.basic_names = []
        self.derived_names = []
        self.fields = {}

    @staticmethod
    def order_changed_cb(order, position, removed, added, config):
        config['order'] = [name.get_string() for name in order]

    def register_field(self, field):
        if field.name in self.names:
            raise RuntimeError("Field '{name}' already registered".format(name=field.name))
        self.names.append(field.name)
        if field.get_value:
            self.derived_names.append(field.name)
        else:
            self.basic_names.append(field.name)
        self.fields[field.name] = field

        field_config = self.config['info'][field.name]
        field.connect('notify', config_notify_cb, field_config)
        if field_config['width'] is not None:
            field.width = field_config['width']
        if field_config['visible'] is not None:
            field.visible = field_config['visible']
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

    def set_derived_fields(self, data):
        for name in self.derived_names:
            value = self.fields[name].get_value(data)
            if value is not None:
                data[name] = value
