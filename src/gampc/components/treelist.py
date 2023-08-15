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

import ampd

# from ..util import data
from . import component
from . import songlist


class Factory(Gtk.SignalListItemFactory):
    def __init__(self):
        super().__init__()

        self.connect('setup', self.setup_cb)
        self.connect('bind', self.bind_cb)
        # self.connect('unbind', self.unbind_cb)
        # self.connect('teardown', self.teardown_cb)

    @staticmethod
    def setup_cb(self, listitem):
        listitem.icon = Gtk.Image()
        listitem.label = Gtk.Label()
        box = Gtk.Box()
        box.append(listitem.icon)
        box.append(listitem.label)
        listitem.expander = Gtk.TreeExpander(child=box)
        listitem.expander.set_focusable(False)
        listitem.set_child(listitem.expander)

    @staticmethod
    def bind_cb(self, listitem):
        row = listitem.get_item()
        node = row.get_item()
        listitem.icon.set_from_icon_name(node.icon)
        listitem.label.set_label(node.joined_path)
        listitem.expander.set_list_row(row)

    # @staticmethod
    # def unbind_cb(self, listitem):
    #     pass

    # @staticmethod
    # def teardown_cb(self, listitem):
    #     self.labels.remove(listitem.label)


class Node(GObject.Object):
    STATE_UNEXPANDED = 0
    STATE_EXPANDED = 1
    STATE_EMPTY = 2

    def __init__(self, name=None, path=None, **kwargs):
        super().__init__()
        self.name = name
        self.path = [] if path is None else path + [name]
        self.joined_path = '/'.join(self.path)
        self.__dict__.update(kwargs)
        self.reset()

    def reset(self):
        self.modified = False
        self.updated = False
        self.state = self.STATE_UNEXPANDED
        self.sub_nodes = Gio.ListStore(item_type=type(self))

    def expand(self):
        if self.state == self.STATE_EMPTY:
            return None
        elif self.state == self.STATE_UNEXPANDED:
            self.state = self.STATE_EXPANDED
            for node in self.sub_nodes:
                node.update()
            self.sub_nodes.connect('items-changed', self.items_changed_cb)
        return self.sub_nodes

    @staticmethod
    def items_changed_cb(model, p, r, a):
        for node in model[p:p + a]:
            node.update()


# class TreeListIconColumn(Gtk.TreeViewColumn):
#     def __init__(self, name):
#         super().__init__(name)
#         icon_cell = Gtk.CellRendererPixbuf()
#         self.pack_start(icon_cell, False)
#         self.set_cell_data_func(icon_cell, self.icon_data_func)
#         name_cell = Gtk.CellRendererText()
#         self.pack_start(name_cell, False)
#         self.set_cell_data_func(name_cell, self.name_data_func)

#     @staticmethod
#     def icon_data_func(self, cell, store, i, param):
#         node = store.get_value(i, 0)
#         cell.set_property('icon-name', node.icon)

#     @staticmethod
#     def name_data_func(self, cell, store, i, param):
#         node = store.get_value(i, 0)
#         if node.modified:
#             cell.set_property('text', '* ' + node.name)
#             cell.set_property('font', 'bold italic')
#         else:
#             cell.set_property('text', node.name)
#             cell.set_property('font', None)


class TreeList(component.ComponentMixinPaned, songlist.SongList):
    def __init__(self, unit):
        super().__init__(unit)
        self.left_store = Gtk.MultiSelection(model=self.init_left_store())
        self.left_view.set_model(self.left_store)

        self.left_view.connect('activate', self.left_view_activate_cb)
        self.left_store.connect('selection_changed', self.left_selection_changed_cb)
        self.left_store.select_item(0, True)

    def shutdown(self):
        super().shutdown()
        self.left_store.disconnect_by_func(self.left_selection_changed_cb)

    def get_left_factory(self):
        return Factory()

    def left_selection_changed_cb(self, selection, position, n_items):
        songs = []
        for i, row in enumerate(selection):
            if selection.is_selected(i):
                songs += row.get_item().songs
        self.set_records(songs)

    @staticmethod
    def left_view_activate_cb(view, position):
        row = view.get_model()[position]
        if row.is_expandable():
            row.set_expanded(not row.get_expanded())
