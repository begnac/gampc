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


import os

import ampd

from ..util import unit
from ..components import treelist
from ..components import songlist
from ..components import browser


DIRECTORY = 'directory'


class __unit__(songlist.UnitMixinPanedSongList, unit.Unit):
    COMPONENT_CLASS = browser.Browser

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.left_store = treelist.TreeStore(self.fill_node, treelist.Node())

    def shutdown(self):
        super().shutdown()
        del self.left_store

    @ampd.task
    async def client_connected_cb(self, client):
        while True:
            await self.left_store.update()
            await self.ampd.idle(ampd.DATABASE)

    async def get_path_contents(self, path):
        if path:
            return await self.ampd.lsinfo('/'.join(path[1:]))
        else:
            return {DIRECTORY: [{DIRECTORY: _("Music")}]}

    async def fill_node(self, node):
        icon = 'folder-symbolic'

        contents = await self.get_path_contents(node.path)
        folders = sorted(os.path.basename(item[DIRECTORY]) for item in contents.get(DIRECTORY, []))
        node.sub_nodes = (dict(name=folder, icon=icon) for folder in folders)
