# coding: utf-8
#
# Graphical Asynchronous Music Player Client
#
# Copyright (C) 2015-2022 Itaï BEN YAACOV
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

import ampd

from ..util import data
from . import component
from . import songlist


class Node(GObject.Object):
    def __init__(self, name=None, icon=None, path=None, **kwargs):
        super().__init__()
        self.name = name
        self.icon = icon
        self.path = [] if path is None else path + [name]
        self.joined_path = '/'.join(self.path)
        self.__dict__.update(kwargs)
        self.sub_nodes = []
        self.songs = []
        self.updated = False
        self.modified = False
        self.update_below = False
        # self.expanded = 0


class TreeStore(data.StoreIterMixin, Gtk.TreeStore):
    def __init__(self, fill_node, root):
        self.node_class = type(root)

        super().__init__(self.node_class)

        self.fill_node = fill_node
        self.root = root

    def init_node(self, i, name, icon, path=[], **kwargs):
        node = self.node_class(name, icon, path, **kwargs)
        self.set_value(i, 0, node)
        return node

    def get_node(self, i):
        return self.root if i is None else self.get_value(i, 0)

    async def update(self):
        await self.update_node(None)

    async def update_node(self, i):
        node = self.get_node(i)
        await self.fill_node(node)
        j = self.iter_children(i)
        for sub_node_data in node.sub_nodes:
            name = sub_node_data['name']
            while j:
                sub_node = self.get_node(j)
                if sub_node.name < name:
                    if not self.remove(j):
                        j = None
                else:
                    break
            if j and sub_node.name == name:
                sub_node.__dict__.update(sub_node_data)
            else:
                j = self.insert_before(i, j)
                self.init_node(j, path=node.path, **sub_node_data)
            j = self.iter_next(j)

        if i is None or node.update_below:
            await self.update_below_node(i)

    async def update_below_node(self, i):
        for j in self.children_iter(i):
            await self.update_node(j)


class TreeListIconColumn(Gtk.TreeViewColumn):
    def __init__(self, name):
        super().__init__(name)
        icon_cell = Gtk.CellRendererPixbuf()
        self.pack_start(icon_cell, False)
        self.set_cell_data_func(icon_cell, self.icon_data_func)
        name_cell = Gtk.CellRendererText()
        self.pack_start(name_cell, False)
        self.set_cell_data_func(name_cell, self.name_data_func)

    @staticmethod
    def icon_data_func(self, cell, store, i, param):
        node = store.get_value(i, 0)
        cell.set_property('icon-name', node.icon)

    @staticmethod
    def name_data_func(self, cell, store, i, param):
        node = store.get_value(i, 0)
        if node.modified:
            cell.set_property('text', '* ' + node.name)
            cell.set_property('font', 'bold italic')
        else:
            cell.set_property('text', node.name)
            cell.set_property('font', None)


class TreeList(songlist.SongList, component.PanedComponent):
    def __init__(self, unit):
        super().__init__(unit)

        col = TreeListIconColumn(self.left_title)
        self.left_treeview.insert_column(col, 0)

        self.left_treeview.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        self.left_treeview.connect('row-activated', self.left_treeview_row_activated_cb)
        self.left_treeview.connect('row-expanded', self.left_treeview_row_expanded_cb)
        self.left_treeview.connect('row-collapsed', self.left_treeview_row_collapsed_cb)

        self.selected_nodes = []
        self.selected_node = None

    @ampd.task
    async def left_treeview_selection_changed_cb(self, *args):
        store, paths = self.left_treeview.get_selection().get_selected_rows()
        self.selected_nodes = [self.left_store.get_node(store.get_iter(p)) for p in paths]
        self.selected_node = self.selected_nodes[0] if len(self.selected_nodes) == 1 else None
        self.set_records(sum([(await self.get_node_songs(node)) for node in self.selected_nodes], []))

    @staticmethod
    def left_treeview_row_activated_cb(left_treeview, p, column):
        if left_treeview.row_expanded(p):
            left_treeview.collapse_row(p)
        else:
            left_treeview.expand_row(p, False)

    @ampd.task
    async def left_treeview_row_expanded_cb(self, left_treeview, i, p):
        self.left_store.get_node(i).update_below = True
        await self.left_store.update_below_node(i)

    def left_treeview_row_collapsed_cb(self, left_treeview, i, p):
        self.left_store.get_node(i).update_below = False
