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


from gi.repository import GLib

import json
import os

from ..util import unit
from ..util.logger import logger

from .. import __application__


class ConfigNode:
    def __init__(self, name, base=None):
        self._name = name
        self._base = base
        self._is_leaf = None
        self._value = None

    def __del__(self):
        logger.debug("Deleting config {}".format(self._name))

    def _get(self, *, default=None):
        if self._is_leaf is False:
            raise RuntimeError

        if self._is_leaf is None:
            self._is_leaf = True
            self._value = self._base if self._base is not None else default

        return self._value

    def _set(self, value):
        if self._is_leaf is False:
            raise RuntimeError(self._name)

        self._is_leaf = True
        self._value = value

    def __getattr__(self, name):
        return self._subnode(name)

    __getitem__ = __getattr__

    def _subnode(self, name, default=None):
        if self._is_leaf is True:
            raise RuntimeError(self._name, name)

        if self._is_leaf is None:
            self._is_leaf = False
            self._value = {}
            if self._base is None:
                self._base = {}
            if not isinstance(self._base, dict):
                raise RuntimeError(self._name)
        elif name in self._value:
            return self._value[name]

        subnode = ConfigNode('.'.join((self._name, name)), self._base.get(name, default))
        self._value[name] = subnode
        return subnode

    def _get_tree(self):
        if self._is_leaf is False:
            return {name: subnode._get_tree() for name, subnode in self._value.items()}
        else:
            return self._value

    def __str__(self):
        return "{}: {} | {}".format(self._name, self._get_tree(), self._base)


class LoadedConfigNode(ConfigNode):
    def __init__(self, name):
        super().__init__(name)
        self._path = os.path.join(GLib.get_user_config_dir(), __application__, self._name + '.json')
        self._load()
        self._is_leaf = False
        self._value = {}

    def _load(self):
        if os.path.exists(self._path):
            self._base = json.loads(open(self._path, 'rb').read().decode('utf-8'))
        else:
            self._base = {}

    def _save(self):
        tree = self._get_tree()
        if tree:
            s = json.dumps(tree, sort_keys=True, indent=2, ensure_ascii=False) + '\n'
            open(self._path, 'wb').write(s.encode('utf-8'))
        elif os.path.exists(self._path):
            os.remove(self._path)


class __unit__(unit.Unit):
    def __init__(self, manager):
        super().__init__(manager)
        self.config_trees = {}

    def cleanup(self):
        super().cleanup()
        for config_tree in self.config_trees.values():
            config_tree._save()

    def load_config(self, name):
        if name in self.config_trees:
            raise RuntimeError
        config_tree = LoadedConfigNode(name)
        self.config_trees[name] = config_tree
        return config_tree
