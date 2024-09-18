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


class Tree:
    def __init__(self):
        self.root = self.get_root()

    def start(self):
        self.root.model.remove_all()
        self.fill_node(self.root)

    def expose(self, node):
        if not node.ready:
            node.ready = True
            self.fill_node(node)
        return node.model

    def children_changed_cb(self, model, p, r, a):
        for child in model[p:p + a]:
            self.fill_node(child)


class Node(GObject.Object):
    def __init__(self, name=None, path=None, leaf=False, **kwargs):
        super().__init__()
        self.name = name
        self.path = [] if path is None else path + [name]
        self.__dict__.update(kwargs)
        self.model = None if leaf else Gio.ListStore()
        self.ready = False

    def __repr__(self):
        return '/'.join(self.path)
