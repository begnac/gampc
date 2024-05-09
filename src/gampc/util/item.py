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


class Item(GObject.Object):
    value = GObject.Property()

    def __init__(self, **kwargs):
        self.bound = {}
        super().__init__(**kwargs)

    def bind(self, widget, name):
        self.bound[name] = widget
        if self.value is not None:
            self._set_bound(name)

    @staticmethod
    def _set_bound(name):
        pass

    def unbind(self, name):
        self._unset_bound(name)
        del self.bound[name]

    @staticmethod
    def _unset_bound(name):
        pass

    def rebind(self):
        for name in self.bound.keys():
            self._set_bound(name)

    def set_value(self, value):
        self.value = value
        self.rebind()


class ItemFromCache(Item):
    def __init__(self, cache, **kwargs):
        self.cache = cache
        self.barrier = {}
        super().__init__(**kwargs)

    def move_barrier(self, name):
        barrier = self.barrier.get(name, 0) + 1
        self.barrier[name] = barrier
        return barrier

    def _set_bound(self, name):
        super()._set_bound(name)
        if self.cache.call_soon(self.set_label, self.value, name, self.move_barrier(name)) is not None:
            self.bound[name].set_label("")

    def set_label(self, data, name, barrier):
        if barrier == self.barrier[name]:
            self.bound[name].set_label(data.get(name, ""))

    def _unset_bound(self, name):
        self.move_barrier(name)
        self.bound[name].set_label("")
        super()._unset_bound(name)

    def set_from_string(self, string):
        self.set_value(string)

    def to_string(self):
        return self.value

    def get_data_now(self):
        return self.cache.get_now(self.value, {'file': self.value})


class ItemWithDict(Item):
    __gsignals__ = {
        'changed': (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.edited_handlers = {}

    def bind(self, widget, name):
        super().bind(widget, name)
        self.edited_handlers[name] = widget.connect('edited', self.edited_cb, name)

    def _set_bound(self, name):
        super()._set_bound(name)
        self.bound[name].label = self.value.get(name, "")

    def unbind(self, name):
        self.bound[name].disconnect(self.edited_handlers.pop(name))
        super().unbind(name)

    def _unset_bound(self, name):
        self.bound[name].set_text("")
        super()._unset_bound(name)

    def edited_cb(self, widget, name):
        self.value[name] = widget.get_text()
        self._set_bound(name)
        self.emit('changed')

    def get_data_now(self):
        return self.value


class ItemListStore(Gio.ListStore):
    def __init__(self, item_factory):
        self.item_factory = item_factory
        super().__init__(item_type=Item)

    def splice_items(self, pos, remove, values):
        values = list(values)
        n = len(values)
        if n > remove:
            self[pos + remove:pos + remove] = [self.item_factory() for _ in range(n - remove)]
        elif remove > n:
            self[pos + n:pos + remove] = []
        for value in values:
            self[pos].set_value(value)
            pos += 1

    def set_items(self, values):
        self.splice_items(0, self.get_n_items(), values)

    def get_strings(self, pos=0, n=None):
        if n is None:
            n = self.get_n_items()
        return [item.to_string() for item in self[pos:pos + n]]