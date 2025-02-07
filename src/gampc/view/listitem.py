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

from ..util.misc import FactoryBase

from ..ui import editable


class ListItemFactory(FactoryBase):
    def __init__(self, name):
        super().__init__()
        self.name = name

    def setup_cb(self, listitem):
        listitem.set_child(self.make_widget())

    def bind_cb(self, listitem):
        listitem.get_item().bind(self.name, listitem.get_child())

    def unbind_cb(self, listitem):
        listitem.get_item().unbind(self.name)


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
