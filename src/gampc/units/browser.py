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

from ..util import record
from ..util import unit
from ..ui import treelist
from ..components import songlistbase
from ..components import songlist


DIRECTORY = 'directory'


class Browser(songlistbase.SongListBasePaneMixin, songlist.SongList):
    sortable = True


class __unit__(songlist.UnitMixinPanedSongList, unit.Unit):
    title = _("Database Browser")
    key = '2'

    COMPONENT_CLASS = Browser

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.root = treelist.TreeNode()
        self.left_store = Gtk.TreeListModel.new(self.root.model, False, False, lambda node: node.expose())

    def shutdown(self):
        super().shutdown()
        del self.root

    @ampd.task
    async def client_connected_cb(self, client):
        while True:
            self.root.update(self.fill_node)
            self.root.expose()
            await self.ampd.idle(ampd.DATABASE)
            self.root.reset()

    async def fill_node(self, node):
        if node.path:
            contents = await self.ampd.lsinfo('/'.join(node.path[1:]))
        else:
            contents = {DIRECTORY: [{DIRECTORY: _("Music")}]}
        folders = sorted(os.path.basename(item[DIRECTORY]) for item in contents.get(DIRECTORY, []))
        node.sub_nodes = [treelist.TreeNode(name=folder, path=node.path, icon='folder-symbolic') for folder in folders]
        songs = contents.get('file', [])
        for song in songs:
            self.unit_songlist.fields.set_derived_fields(song)
        node.records = list(map(record.Record, songs))
