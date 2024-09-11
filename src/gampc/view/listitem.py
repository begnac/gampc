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
from gi.repository import Gtk

from ..util import misc

from ..ui import editable


class ListItemFactoryBase(Gtk.SignalListItemFactory):
    def __init__(self, name):
        super().__init__()

        self.name = name

        self.binders = []
        self.binders.append(('value', self.value_binder, name))

        self.connect('setup', self.setup_cb)
        self.connect('bind', self.bind_cb)
        self.connect('unbind', self.unbind_cb)
        # self.connect('teardown', self.teardown_cb)

    @staticmethod
    def setup_cb(self, listitem):
        listitem.set_child(self.make_widget())

    @staticmethod
    def bind_cb(self, listitem):
        widget = listitem.get_child()
        widget.pos = listitem.get_position()
        self.bind(widget, listitem.get_item())

    @staticmethod
    def unbind_cb(self, listitem):
        self.unbind(listitem.get_child(), listitem.get_item())

    # @staticmethod
    # def teardown_cb(self, listitem):
    #     pass

    def bind(self, widget, item_):
        for name, binder, *args in self.binders:
            binder(widget, item_, *args)
        item_.connect('notify', self.notify_item_cb, widget)

    def unbind(self, widget, item_):
        item_.disconnect_by_func(self.notify_item_cb)

    def notify_item_cb(self, item_, param, widget):
        for name, binder, *args in self.binders:
            if name == param.name:
                binder(widget, item_, *args)

    @staticmethod
    def value_binder(widget, item_, name):
        value = item_.get_field(name)
        widget.set_label(value)


class ListItemFactory(ListItemFactoryBase):
    def __init__(self, name):
        super().__init__(name)

        self.binders.append(('value', self.key_binder))
        self.binders.append(('duplicate', self.duplicate_binder))

    @staticmethod
    def key_binder(widget, item_):
        misc.add_unique_css_class(widget.get_parent(), 'key', item_.get_key().encode().hex())

    @staticmethod
    def duplicate_binder(widget, item_):
        if item_.duplicate is None:
            suffix = None
        else:
            suffix = str(item_.duplicate % 64)
        misc.add_unique_css_class(widget.get_parent(), 'duplicate', suffix)


class LabelListItemFactory(ListItemFactory):
    @staticmethod
    def make_widget():
        return Gtk.Label(halign=Gtk.Align.START)


class EditableListItemFactoryBase(ListItemFactoryBase):
    __gsignals__ = {
        'item-edited': (GObject.SIGNAL_RUN_FIRST, None, (int, str, str)),
    }

    def make_widget(self):
        widget = editable.EditableLabel()
        widget.connect('edited', self.edited_cb, self.name)
        return widget

    def edited_cb(self, widget, text, name):
        self.emit('item-edited', widget.pos, name, text)

    @staticmethod
    def start_editing_cb(cell, arg):
        cell.get_first_child().start_editing()


class EditableListItemFactory(EditableListItemFactoryBase, ListItemFactory):
    pass
