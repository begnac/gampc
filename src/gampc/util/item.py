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

from . import misc


class BaseItem(GObject.Object):
    value = GObject.Property()

    def __init__(self, *, value=None):
        super().__init__()
        if value is not None:
            self.new_value(value)

    def new_value(self, value):
        self.value = value

    def get_field(self, name, default=None):
        return self.value.get(name, default)


class Item(BaseItem):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._widgets = []

        self.connect('notify', self.__class__.notify_cb)

    def bind(self, widget):
        assert widget not in self._widgets
        widget._item = self
        self._widgets.append(widget)
        for prop, binder in self.get_binders():
            binder(widget)

    def unbind(self, widget):
        assert widget in self._widgets
        self._widgets.remove(widget)
        del widget._item

    def notify_cb(self, param):
        for prop, binder in self.get_binders():
            if prop == param.get_name():
                for widget in self._widgets:
                    binder(widget)

    def get_binders(self):
        yield 'value', self.value_binder

    def value_binder(self, widget):
        widget.set_label(str(self.get_field(widget.get_name(), '')))


class SongItem(Item):
    duplicate = GObject.Property()

    def get_key(self):
        return self.value['file']

    def new_value(self, value):
        self.duplicate = None
        super().new_value(value)

    def get_binders(self):
        yield from super().get_binders()
        yield 'duplicate', self.duplicate_binder

    def value_binder(self, widget):
        super().value_binder(widget)
        misc.add_unique_css_class(widget.get_parent(), 'key', self.get_key().encode().hex())

    def duplicate_binder(self, widget):
        if self.duplicate is None:
            suffix = None
        else:
            suffix = str(self.duplicate % 64)
        misc.add_unique_css_class(widget.get_parent(), 'duplicate', suffix)


class ListItemFactory(misc.FactoryBase):
    def __init__(self, name, widget_factory, edit_manager=None):
        super().__init__()
        self.name = name
        self.widget_factory = widget_factory
        self.edit_manager = edit_manager

    def setup_cb(self, listitem):
        listitem.set_child(self.widget_factory(name=self.name))

    def bind_cb(self, listitem):
        listitem.get_item().bind(listitem.get_child())

    def unbind_cb(self, listitem):
        listitem.get_item().unbind(listitem.get_child())


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
            items[i].new_value(values[i])
        self[pos:pos + remove] = items[:n]


class TransferBase(GObject.Object):
    value = GObject.Property()

    def get_content(self):
        return Gdk.ContentProvider.new_for_value(self)


class PartialTransfer(TransferBase):
    def __init__(self, changes):
        super().__init__(value=changes)


class PartialStringTransfer(PartialTransfer):
    def get_content(self):
        return Gdk.ContentProvider.new_for_value(repr(self.value))


class ItemValueTransfer(TransferBase):
    def __init__(self, items):
        super().__init__(value=[item.value for item in items])


class ItemKeyTransfer(TransferBase):
    def __init__(self, items):
        super().__init__(value=[item.get_key() for item in items])


class ItemStringTransfer(ItemKeyTransfer):
    def get_content(self):
        return Gdk.ContentProvider.new_for_value(repr(self.value))


def transfer_union(value, *transfers):
    return Gdk.ContentProvider.new_union([transfer(value).get_content() for transfer in transfers])


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
