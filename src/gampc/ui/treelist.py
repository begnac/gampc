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

import asyncio
import ampd


class TreeNode(GObject.Object):
    STATE_UNEXPOSED = 0
    STATE_EXPOSED = 1

    def __init__(self, name=None, path=None, **kwargs):
        super().__init__()
        self.name = name
        self.path = [] if path is None else path + [name]
        self.joined_path = '/'.join(self.path)
        self.__dict__.update(kwargs)
        self.model = Gio.ListStore(item_type=type(self))
        self.reset()

    def __del__(self):
        self.model.remove_all()

    def reset(self):
        self.filled_sub_nodes = False
        self.filled_contents = False
        self.state = self.STATE_UNEXPOSED
        self.model.remove_all()
        self.sub_nodes = []

    def append_sub_node(self, node):
        self.sub_nodes.append(node)
        node.parent_model = self.model
        node.fill_sub_nodes_cb = self.fill_sub_nodes_cb
        node.fill_contents_cb = self.fill_contents_cb

    def expose(self):
        if self.state == self.STATE_UNEXPOSED:
            assert self.filled_sub_nodes is True
            self.state = self.STATE_EXPOSED
            for node in self.sub_nodes:
                node.fill_sub_nodes()
            self.fill_contents()
        return self.model if self.sub_nodes else None

    def fill_sub_nodes(self):
        if self.filled_sub_nodes is False:
            self.filled_sub_nodes = asyncio.create_task(self._fill_sub_nodes())
            return self.filled_sub_nodes

    async def _fill_sub_nodes(self):
        try:
            await self.fill_sub_nodes_cb(self)
        except ampd.ConnectionError:
            return
        self.filled_sub_nodes = True
        if self.state == self.STATE_EXPOSED:
            for node in self.sub_nodes:
                node.fill_sub_nodes()
        if self.parent_model is not None:
            self.parent_model.append(self)

    def fill_contents(self):
        if self.filled_contents is False:
            self.filled_contents = asyncio.create_task(self._fill_contents())

    async def _fill_contents(self):
        if self.filled_sub_nodes is not True:
            await self.filled_sub_nodes
        try:
            await self.fill_contents_cb(self)
        except ampd.ConnectionError:
            return
        self.filled_contents = True
