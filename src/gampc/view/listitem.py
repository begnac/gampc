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
from gi.repository import Gtk

from ..util import misc

from ..ui import editable


class FactoryBase(Gtk.SignalListItemFactory):
    def __init__(self):
        super().__init__()
        self.connect('setup', self.__class__.setup_cb)
        self.connect('bind', self.__class__.bind_cb)
        self.connect('unbind', self.__class__.unbind_cb)
        self.connect('teardown', self.__class__.teardown_cb)

    def setup_cb(self, listitem):
        pass

    def bind_cb(self, listitem):
        pass

    def unbind_cb(self, listitem):
        pass

    def teardown_cb(self, listitem):
        pass


class RowFactory(FactoryBase):
    def bind_cb(self, listitem):
        listitem.get_item()._position = listitem.get_position()
        listitem.connect('notify::position', self.__class__.notify_position_cb)

    def unbind_cb(self, listitem):
        listitem.disconnect_by_func(self.__class__.notify_position_cb)
        del listitem.get_item()._position

    def notify_position_cb(listitem, param):
        listitem.get_item()._position = listitem.get_position()
        print(listitem, listitem.get_position(), listitem.get_item())


class ListItemFactory(FactoryBase):
    def __init__(self, name):
        super().__init__()
        self.name = name

    def setup_cb(self, listitem):
        listitem.set_child(self.make_widget())

    def bind_cb(self, listitem):
        widget = listitem.get_child()
        widget.pos = listitem.get_position()
        listitem.get_item().bind(self.name, widget)

    def unbind_cb(self, listitem):
        item_ = listitem.get_item()
        item_.unbind(self.name)


class LabelListItemFactory(ListItemFactory):
    @staticmethod
    def make_widget():
        return Gtk.Label(halign=Gtk.Align.START)


class EditableListItemFactory(ListItemFactory):
    __gsignals__ = {
        'item-edited': (GObject.SIGNAL_RUN_FIRST, None, (int, str, str)),
    }

    def make_widget(self, factory=editable.EditableLabel):
        widget = factory()
        widget.connect('edited', self.edited_cb, self.name)
        return widget

    def edited_cb(self, widget, text, name):
        self.emit('item-edited', widget.pos, name, text)
