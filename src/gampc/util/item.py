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
from gi.repository import GObject
from gi.repository import Gio
from gi.repository import Gdk

from . import misc


class BaseItem(GObject.Object):
    value = GObject.Property()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.value is not None:
            GLib.idle_add(lambda: self.notify('value'))

    def get_field(self, name, default=None):
        return self.value.get(name, default)


class Item(BaseItem):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._row = None
        self._widgets = {}

        self.connect('notify::value', self.__class__.notify_value_cb)
        self.connect('notify', self.__class__.notify_cb)

    def bind(self, name, widget):
        widget._item = self
        self._widgets[name] = widget
        for prop, binder in self.get_binders():
            binder(name, widget)
        if self._row is None:
            self._row = GLib.idle_add(self.tweak_row, widget)

    def unbind(self, name):
        del self._widgets[name]

    def notify_cb(self, param):
        for prop, binder in self.get_binders():
            if prop == param.get_name():
                for name, widget in self._widgets.items():
                    binder(name, widget)

    def notify_value_cb(self, param):
        pass

    def get_binders(self):
        yield 'value', self.value_binder

    def value_binder(self, name, widget):
        widget.set_label(self.get_field(name, ''))

    def tweak_row(self, widget):
        cell = widget.get_parent()
        self._row = cell and cell.get_parent()
        if self._row:
            misc.remove_control_move_shortcuts(self._row)


class SongItem(Item):
    duplicate = GObject.Property()

    def get_key(self):
        return self.value['file']

    def notify_value_cb(self, param):
        self.duplicate = None
        super().notify_value_cb(param)

    def get_binders(self):
        yield from super().get_binders()
        yield 'duplicate', self.duplicate_binder

    def value_binder(self, name, widget):
        super().value_binder(name, widget)
        misc.add_unique_css_class(widget.get_parent(), 'key', self.get_key().encode().hex())

    def duplicate_binder(self, name, widget):
        if self.duplicate is None:
            suffix = None
        else:
            suffix = str(self.duplicate % 64)
        misc.add_unique_css_class(widget.get_parent(), 'duplicate', suffix)


class ItemListStore(Gio.ListStore):
    def __init__(self, *, item_type, values=None):
        super().__init__(item_type=item_type)
        if values is not None:
            self.set_values(values)

    def set_values(self, values):
        self.splice_values(0, None, values)

    def splice_values(self, pos, remove, values):
        if remove is None:
            remove = self.get_n_items()
        values = list(values)
        n = len(values)
        new_items = [] if remove >= n else [self.get_item_type().pytype() for i in range(n - remove)]
        items = self[pos:pos + remove] + new_items
        for i in range(n):
            items[i].value = values[i]
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
