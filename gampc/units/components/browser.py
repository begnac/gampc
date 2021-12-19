# coding: utf-8
#
# Graphical Asynchronous Music Player Client
#
# Copyright (C) 2015 Itaï BEN YAACOV
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

from gampc.util import component

from gampc.units import songlist


class Browser(songlist.SongListWithEditDelFile, component.PanedComponent):
    title = _("Database Browser")
    name = 'browser'
    key = '2'

    sortable = True

    def __init__(self, unit):
        super().__init__(unit)

        col = Gtk.TreeViewColumn(_("Directory"))
        col.pack_start(Gtk.CellRendererPixbuf(icon_name='folder-symbolic'), False)
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, False)
        col.add_attribute(renderer, 'text', 2)
        self.left_treeview.insert_column(col, 0)

        self.left_treeview.connect('row-activated', self.left_treeview_row_activated_cb)
        self.left_treeview.connect('row-expanded', self.left_treeview_row_expanded_cb)

        self.init_store()

    def init_store(self):
        self.left_store = Gtk.TreeStore()
        self.left_store.set_column_types([str, bool, str])
        i = self.left_store.append(None)
        self.left_store.set(i, {0: '', 1: False, 2: _("Music database")})

        self.left_treeview.set_model(self.left_store)
        self.left_treeview.set_cursor(self.left_store.get_path(i))

    def action_reset_cb(self, action, parameter):
        super().action_reset_cb(action, parameter)
        cwd = self.cwd
        self.init_store()
        if cwd:
            self.expand_path(cwd)

    @ampd.task
    async def expand_path(self, cwd):
        i = self.left_store.get_iter_first()
        for element in cwd.split('/'):
            await self._read_directories(i)
            j = self.left_store.iter_children(i)
            while j:
                if element == self.left_store.get_value(j, 2):
                    i = j
                    break
                else:
                    j = self.left_store.iter_next(j)
            else:
                break
        path = self.left_store.get_path(i)
        self.left_treeview.expand_to_path(path)
        self.left_treeview.set_cursor(path)

    async def _read_directories(self, i):
        if self.left_store.get_value(i, 1):
            return
        row = Gtk.TreeRowReference.new(self.left_store, self.left_store.get_path(i))
        contents = await self.ampd.lsinfo(self.left_store.get_value(i, 0))
        i = self.left_store.get_iter(row.get_path())
        self.left_store.set_value(i, 1, True)
        directories = sorted(item['directory'] for item in contents.get('directory', []))
        j = self.left_store.iter_children(i)
        while j or directories:
            if not j or (directories and directories[0] < self.left_store.get_value(j, 0)):
                j = self.left_store.insert_before(i, j)
                self.left_store.set(j, {0: directories[0], 1: False, 2: os.path.basename(directories[0])})
            elif directories and self.left_store.get_value(j, 0) == directories[0]:
                self.left_store.set_value(j, 1, False)
            else:
                if not self.left_store.remove(j):
                    j = None
                continue
            directories.pop(0)
            if self.left_treeview.row_expanded(self.left_store.get_path(i)):
                self.read_directories(j)
            else:
                while self.left_store.iter_children(j):
                    self.left_store.remove(self.left_store.iter_children(j))
            j = self.left_store.iter_next(j)

    read_directories = ampd.task(_read_directories)

    @ampd.task
    async def read_files(self, *args):
        contents = await self.ampd.lsinfo(self.cwd)
        self.set_records(contents.get('file', []))

    def left_treeview_selection_changed_cb(self, *args):
        store, i = self.left_treeview.get_selection().get_selected()
        if not i:
            return
        self.cwd = self.left_store.get_value(i, 0)
        self.read_directories(i)
        self.read_files()

    @ampd.task
    async def client_connected_cb(self, client):
        while True:
            self.left_store.set_value(self.left_store.get_iter_first(), 1, False)
            self.read_directories(self.left_store.get_iter_first())
            self.read_files()
            await self.ampd.idle(ampd.DATABASE)

    def left_treeview_row_activated_cb(self, left_treeview, p, column):
        if left_treeview.row_expanded(p):
            left_treeview.collapse_row(p)
        else:
            left_treeview.expand_row(p, False)

    def left_treeview_row_expanded_cb(self, left_treeview, i, p):
        j = self.left_store.iter_children(i)
        while j:
            self.read_directories(j)
            j = self.left_store.iter_next(j)


class __unit__(songlist.UnitWithPanedSongList):
    MODULE_CLASS = Browser
