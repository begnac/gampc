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

import asyncio
import ampd


class TreeItemFactory(Gtk.SignalListItemFactory):
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
        box = Gtk.Box(spacing=4)
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
        listitem.label.set_label(node.name)
        listitem.expander.set_list_row(row)
        row.name = node.name

    # @staticmethod
    # def unbind_cb(self, listitem):
    #     pass

    # @staticmethod
    # def teardown_cb(self, listitem):
    #     self.labels.remove(listitem.label)


class TreeNode(GObject.Object):
    STATE_UNEXPOSED = 0
    STATE_EXPOSED = 1
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
        self.state = self.STATE_UNEXPOSED
        self.sub_nodes = []
        self.model = Gio.ListStore(item_type=type(self))

    def expose(self):
        if self.state == self.STATE_EMPTY:
            return None
        elif self.state == self.STATE_UNEXPOSED:
            self.state = self.STATE_EXPOSED
            assert self.updated is not False
            if self.updated is True:
                for node in self.sub_nodes:
                    node.update(*self.filler, model=self.model)
        return self.model

    def update(self, *filler, model=None):
        self.filler = filler
        if self.updated is False:
            self.updated = asyncio.ensure_future(self._update(model))

    async def _update(self, model):
        filler, *args = self.filler
        try:
            await filler(self, *args)
        except ampd.ConnectionError:
            pass
        self.updated = True
        if not self.sub_nodes:
            self.state = self.STATE_EMPTY
        elif self.state == self.STATE_EXPOSED:
            for node in self.sub_nodes:
                node.update(*self.filler, model=self.model)
        if model is not None:
            model.append(self)


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
