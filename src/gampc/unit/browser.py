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


import os

import ampd

from ..util import unit

from ..ui import compound
from ..ui import treelist

from ..view.cache import ViewCacheWithCopy

from ..components import songlist

from . import mixins


DIRECTORY = 'directory'


class BrowserWidget(compound.WidgetWithPanedTreeList):
    def left_selection_changed_cb(self, selection, position, n_items):
        super().left_selection_changed_cb(selection, position, n_items)
        self.main.set_keys(sum((selection[pos].get_item().keys for pos in self.left_selection_pos), []))


class Browser(songlist.SongList):
    def __init__(self, unit):
        super().__init__(unit)
        self.widget = BrowserWidget(self.view, self.config.pane_separator, unit.root.model)
        self.connect_clean(self.unit.root.model, 'items-changed', self.root_items_changed_cb)
        if len(self.widget.left_selection) > 0:
            self.widget.left_selection[0].set_expanded(True)

    def create_view(self):
        return super().create_view(ViewCacheWithCopy, cache=self.unit.unit_database.cache)

    def root_items_changed_cb(self, model, p, r, a):
        if a:
            self.widget.left_selection[0].set_expanded(True)


class __unit__(mixins.UnitPanedComponentMixin, unit.Unit):
    title = _("Database Browser")
    key = '2'

    COMPONENT_CLASS = Browser

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.require('database')
        self.require('fields')
        self.require('persistent')

        self.root = treelist.TreeNode(parent_model=None, fill_sub_nodes_cb=self.fill_sub_nodes_cb, fill_contents_cb=self.fill_contents_cb)

    def cleanup(self):
        del self.root
        super().cleanup()

    @ampd.task
    async def client_connected_cb(self, client):
        while True:
            self.root.reset()
            await self.root.fill_sub_nodes()
            self.root.expose()
            await self.ampd.idle(ampd.DATABASE)

    async def fill_sub_nodes_cb(self, node):
        if node.path:
            contents = await self.ampd.lsinfo('/'.join(node.path[1:]))
        else:
            contents = {DIRECTORY: [{DIRECTORY: _("Music")}]}
        for folder in sorted(os.path.basename(item[DIRECTORY]) for item in contents.get(DIRECTORY, [])):
            node.append_sub_node(treelist.TreeNode(name=folder, path=node.path, icon='folder-symbolic'))
        node.keys = [data['file'] for data in contents.get('file', [])]

    async def fill_contents_cb(self, node):
        pass
