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
from gi.repository import Gdk


class ItemBase(GObject.Object):
    value = GObject.Property()

    def __init__(self, value=None):
        super().__init__()
        if value is not None:
            self.load(value)

    def load(self, value):
        self.value = value

    def get_field(self, name, default=''):
        return self.value.get(name, default)


class Item(ItemBase):
    duplicate = GObject.Property()

    def load(self, value):
        super().load(value)
        self.duplicate = None

    def get_key(self):
        return self.value['file']


class ItemListStore(Gio.ListStore):
    def __init__(self, item_type=Item, values=None):
        super().__init__(item_type=item_type)
        self.item_type = item_type
        if values is not None:
            self.set_values(values)

    def set_values(self, values):
        self.splice_values(0, None, values)

    def splice_values(self, pos, remove, values):
        if remove is None:
            remove = self.get_n_items()
        values = list(values)
        n = len(values)
        new_items = [] if remove >= n else [self.item_type() for i in range(n - remove)]
        items = self[pos:pos + remove] + new_items
        for i in range(n):
            items[i].load(values[i])
        self[pos:pos + remove] = items[:n]


class ItemTransfer(GObject.Object):
    values = GObject.Property()

    def get_content(self):
        return Gdk.ContentProvider.new_for_value(self)


class ItemValueTransfer(ItemTransfer):
    def __init__(self, items):
        super().__init__(values=[item.value for item in items])


class ItemKeyTransfer(ItemTransfer):
    def __init__(self, items):
        super().__init__(values=[item.get_key() for item in items])


class ItemStringTransfer(ItemKeyTransfer):
    def get_content(self):
        return Gdk.ContentProvider.new_for_value(repr(self.values))


def transfer_union(items, *transfers):
    return Gdk.ContentProvider.new_union([transfer(items).get_content() for transfer in transfers])


def setup_find_duplicate_items(model, test_fields, ignore):
    model.connect('items-changed', lambda m, p, r, a, t, i: find_duplicate_items(m, t, i), test_fields, ignore)


def find_duplicate_items(items, test_fields, ignore):
    marker = 0
    firsts = {}
    for i, item in enumerate(items):
        if item.get_key() in ignore:
            continue
        test = tuple(item.get_field(name) for name in test_fields)
        first = firsts.get(test)
        if first is None:
            firsts[test] = i
            if item.duplicate is not None:
                item.duplicate = None
        else:
            if items[first].duplicate is None:
                items[first].duplicate = marker
                marker += 1
            item.duplicate = items[first].duplicate
