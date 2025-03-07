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


import collections
import json
import os

from gi.repository import GLib

from .. import __application__


class Item:
    def __init__(self, type_, /, *, default=None, is_valid=lambda value: True):
        self.type_ = type_
        self._is_valid = is_valid
        self.default = default

    def is_valid(self, value):
        return isinstance(value, self.type_) and self._is_valid(value)

    def load(self, value=None):
        return value if self.is_valid(value) else self.default


class Dict(Item):
    def __init__(self, other=None, /, **fields):
        super().__init__(dict, default={})
        self.fields = fields
        self.other = other

    def load(self, value=None):
        value = super().load(value)
        if self.other is None:
            result = dict()
        else:
            result = collections.defaultdict(self.other.load)
            result.update({key: self.other.load(item) for key, item in value.items() if key not in self.fields and self.other.is_valid(item)})
        result.update({key: definition.load(value.get(key)) for key, definition in self.fields.items()})
        return result


class List(Item):
    def __init__(self, definition, **kwargs):
        super().__init__(list, default=[], **kwargs)
        self.definition = definition

    def load(self, value=None):
        value = super().load(value)
        return [self.definition.load(item) for item in value if self.definition.is_valid(item)]


def load_json(name, definition):
    path = get_config_path(name)
    value = json.load(open(path)) if os.path.exists(path) else None
    return definition.load(value)


def save_json(name, value):
    path = get_config_path(name)
    json.dump(value, open(path, 'w'), sort_keys=True, indent=2, ensure_ascii=False)


def get_config_path(name):
    return os.path.join(GLib.get_user_config_dir(), __application__, name + '.json')
