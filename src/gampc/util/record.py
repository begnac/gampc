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


class Record(GObject.Object):
    __gsignals__ = {
        'changed': (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, data=None):
        super().__init__()
        self.set_data(data or {})

    def set_data(self, data):
        super().__setattr__('_data', data)
        self.emit('changed')

    def get_data(self):
        return self._data

    def get_data_clean(self):
        return {key: value for key, value in self._data.items() if key[0] != '_'}

    def get(self, *args):
        return self._data.get(*args)

    def __getattr__(self, name):
        return self._data.get(name)

    def __setattr__(self, name, value):
        self._data[name] = value

    def __delattr__(self, name):
        self._data.pop(name, None)

    __getitem__ = __getattr__
    __setitem__ = __setattr__
    __delitem__ = __delattr__

    def items(self):
        return self._data.items()

    def do_changed(self):
        pass


class RecordListStore(Gio.ListStore):
    def __init__(self):
        super().__init__(item_type=Record)

    def set_records(self, records):
        if not records:
            self.remove_all()
            return
        n = self.get_n_items()
        for i, record in enumerate(records):
            if i < n:
                self[i] = record
            else:
                self.append(record)
        i += 1
        if n > i:
            self[i:] = []
