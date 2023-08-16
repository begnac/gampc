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

import ampd

from ..util import unit
from ..ui import treelist
from ..components import songlistbase
from ..components import songlist


DIRECTORY = 'directory'


class BrowserNode(treelist.TreeNode):
    def update(self, cb=None, *cb_args):
        if self.updated is False:
            self.updated = self._update(cb, *cb_args)

    @ampd.task
    async def _update(self, cb, *cb_args):
        if self.path:
            contents = await self.ampd.lsinfo('/'.join(self.path[1:]))
        else:
            contents = {DIRECTORY: [{DIRECTORY: _("Music")}]}
        folders = sorted(os.path.basename(item[DIRECTORY]) for item in contents.get(DIRECTORY, []))
        if not folders:
            self.state = self.STATE_EMPTY
        else:
            for folder in folders:
                self.sub_nodes.append(BrowserNode(name=folder, path=self.path, icon='folder-symbolic', ampd=self.ampd))
        self.songs = contents.get('file', [])
        self.updated = True
        if cb is not None:
            cb(*cb_args)


class Browser(songlistbase.SongListBaseWithPane, songlist.SongList):
    sortable = True


class __unit__(songlist.UnitMixinPanedSongList, unit.Unit):
    title = _("Database Browser")
    key = '2'

    COMPONENT_CLASS = Browser

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.root = BrowserNode(ampd=self.ampd)
        self.left_store = Gtk.TreeListModel.new(self.root.expose(), False, False, lambda node: node.expose())

    def shutdown(self):
        super().shutdown()
        del self.left_store

    @ampd.task
    async def client_connected_cb(self, client):
        while True:
            self.root.update()
            await self.ampd.idle(ampd.DATABASE)
            self.root.reset()
