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

from ..util import config


def get_fields_config():
    return config.Dict(
        info=config.Dict(config.Dict(
            visible=config.Item(bool),
            width=config.Item(int, default=30, is_valid=lambda w: w >= 30),
        )),
        order=config.List(config.Item(str)),
    )


def config_notify_cb(obj, param, config):
    config[param.name] = obj.get_property(param.name)


class FieldInfo(GObject.Object):
    width = GObject.Property(type=int)

    def __init__(self, config, name, *, title=None, sort_default='', min_width=50):
        super().__init__()
        self.config = config
        self.name = name
        self.title = title
        self.min_width = min_width
        self.connect('notify::width', self.__class__.notify_width_cb)
        self.width = self.config['width']
        self.sort_default = sort_default

    def notify_width_cb(self, param):
        if self.width < self.min_width:
            self.width = self.min_width
        else:
            self.config['width'] = self.width

    # def __repr__(self):
    #     return f"Field '{self.name}'"


class FieldsInfo(GObject.Object):
    order = GObject.Property(type=object)

    def __init__(self, config, fields):
        super().__init__()
        self.config = config
        order = [name for name in config['order'] if name in fields]
        self.infos = {}
        for name, kwargs in fields.items():
            self.infos[name] = FieldInfo(config['info'][name], name, **kwargs)
            if name not in order:
                order.append(name)
        self.order = config['order'] = order
