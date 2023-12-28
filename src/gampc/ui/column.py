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
from gi.repository import Gtk


class FieldColumnFactory(Gtk.SignalListItemFactory):
    def __init__(self, widget):
        self.widget = widget
        self.bound = Gio.ListStore()

        super().__init__()

        self.connect('setup', self.setup_cb)
        self.connect('bind', self.bind_cb)
        self.connect('unbind', self.unbind_cb)
        # self.connect('teardown', self.teardown_cb)

    @staticmethod
    def setup_cb(self, listitem):
        listitem.child = self.widget()
        listitem.set_child(listitem.child)

    @staticmethod
    def bind_cb(self, listitem):
        cell = listitem.child.get_parent()
        cell._pos = listitem.get_position()
        self.bound.append(listitem)

    @staticmethod
    def unbind_cb(self, listitem):
        found, position = self.bound.find(listitem)
        self.bound.remove(position)

    # @staticmethod
    # def teardown_cb(self, listitem):
    #     pass


class FieldColumn(Gtk.ColumnViewColumn):
    def __init__(self, name, field, widget, sortable):
        self.name = name

        super().__init__(factory=FieldColumnFactory(widget))

        field.bind_property('title', self, 'title', GObject.BindingFlags.SYNC_CREATE)
        field.bind_property('visible', self, 'visible', GObject.BindingFlags.SYNC_CREATE)
        field.bind_property('width', self, 'fixed-width', GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.BIDIRECTIONAL)

        self.set_resizable(True)

        if sortable:
            sorter = Gtk.CustomSorter.new(self.sort_func, name)
            self.set_sorter(sorter)

    @staticmethod
    def sort_func(record1, record2, name):
        s1 = record1[name] or ''
        s2 = record2[name] or ''
        return Gtk.Ordering.LARGER if s1 > s2 else Gtk.Ordering.SMALLER if s1 < s2 else Gtk.Ordering.EQUAL
