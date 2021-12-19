# coding: utf-8
#
# Graphical Asynchronous Music Player Client
#
# Copyright (C) 2015 Itaï BEN YAACOV
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


import xdg.BaseDirectory
import json
import os

from gampc.util import unit
from gampc.util.logger import logger


class ConfigTree(object):
    def __init__(self, name, base=None):
        if base is None:
            self.__dict__.update(_base={}, _name=name + '/', _dict={}, _loaded=set())
            self._load(name)
        else:
            self.__dict__.update(_base=base, _name=name + '/', _dict={}, _loaded=set())

    def __del__(self):
        logger.debug("Deleting config {}".format(self._name))

    def subtree(self, name):
        self._loaded.add(name)
        result = self.access(name, {})
        result._load(name)
        return result

    def _load(self, name):
        self.__dict__['_filename'] = name + '.json'

        for path in xdg.BaseDirectory.load_config_paths('gampc'):
            fullpath = os.path.join(path, self._filename)
            if os.path.exists(fullpath):
                self._base = json.loads(open(fullpath, 'rb').read().decode('utf-8'))
                break

    def save(self):
        for name in self._loaded:
            self._dict[name].save()
            del self._dict[name]
        to_save = self.get_dict()
        path = os.path.join(xdg.BaseDirectory.save_config_path('gampc'), self._filename)
        if to_save:
            s = json.dumps(to_save, sort_keys=True, indent=2, ensure_ascii=False)
            open(path, 'wb').write(s.encode('utf-8'))
        elif os.path.exists(path):
            os.remove(path)

    def __getattr__(self, name):
        return self.access(name)

    def __setattr__(self, name, value):
        if name in self.__dict__:
            self.__dict__[name] = value
        else:
            self[name] = value

    __getitem__ = __getattr__

    def __setitem__(self, name, value):
        self._dict[name.replace('_', '-')] = value

    def get_dict(self):
        return {key: value.get_dict() if isinstance(value, ConfigTree) else value for key, value in self._dict.items()}

    def access(self, name, default={}):
        name = name.replace('_', '-')
        if name not in self._dict:
            self._dict[name] = self.access_base(name, default)
        return self._dict[name]

    def access_base(self, name, default):
        value = self._base.get(name, default)
        return ConfigTree(self._name + name, value) if isinstance(value, dict) else value

    def __str__(self):
        return "{}: {} | {}".format(self._name, self.get_dict(), self._base)


class __unit__(unit.Unit):
    CONFIG_EDIT_DIALOG_SIZE = 'edit-dialog-size'

    def __init__(self, name, manager):
        super().__init__(name, manager)
        self.config = ConfigTree('config')

    def shutdown(self):
        super().shutdown()
        self.config.save()
