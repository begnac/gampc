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


class List(GObject.Object, Gio.ListModel):
    def __init__(self):
        GObject.Object.__init__(self)
        self.data = []

    def do_get_item_type(self):
        return None

    def do_get_item(self, position):
        try:
            return self.data[position]
        except IndexError:
            return None

    def do_get_n_items(self):
        return len(self.data)

    def splice(self, pos, r, a):
        self.data[pos:pos + r] = a
        self.emit('items-changed', pos, r, len(a))
