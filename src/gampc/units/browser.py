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


from gi.repository import Gtk

import os
import asyncio

import ampd

from ..util import unit

from ..components import treelist
from ..components import songlist
from ..components import browser


DIRECTORY = 'directory'


class BrowserNode(treelist.Node):
    async def get_path_contents(self, path):
        if path:
            return await self.ampd.lsinfo('/'.join(path[1:]))
        else:
            return {DIRECTORY: [{DIRECTORY: _("Music")}]}

    def update(self):
        if self.updated is False:
            self.updated = self._update()

    @ampd.task
    async def _update(self):
        contents = await self.get_path_contents(self.path)
        folders = sorted(os.path.basename(item[DIRECTORY]) for item in contents.get(DIRECTORY, []))
        if not folders:
            self.state = self.STATE_EMPTY
        else:
            for folder in folders:
                self.sub_nodes.append(BrowserNode(name=folder, path=self.path, icon='folder-symbolic', ampd=self.ampd))
        self.songs = contents.get('file', [])
        self.updated = True


class __unit__(songlist.UnitMixinPanedSongList, unit.Unit):
    title = _("Database Browser")
    key = '2'

    COMPONENT_CLASS = browser.Browser

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.root = BrowserNode(ampd=self.ampd)
        self.left_store = Gtk.TreeListModel.new(self.root.expand(), False, False, lambda node: node.expand())

    def shutdown(self):
        super().shutdown()
        del self.left_store

    @ampd.task
    async def client_connected_cb(self, client):
        while True:
            self.root.update()
            await self.ampd.idle(ampd.DATABASE)
            self.root.reset()

    async def fill_node(self, node):
        icon = 'folder-symbolic'

        contents = await self.get_path_contents(node.path)
        folders = sorted(os.path.basename(item[DIRECTORY]) for item in contents.get(DIRECTORY, []))
        node.sub_nodes = (dict(name=folder, icon=icon) for folder in folders)
