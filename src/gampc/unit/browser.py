"""Graphical Asynchronous Music Player Client."""

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

from gi.repository import Gio
from gi.repository import Gtk

import ampd

from ..util import config
from ..util import item as _item
from ..util import misc
from ..util import unit

from ..view.actions import ViewWithCopy

from ..control import lefttree

from . import mixins


DIRECTORY = 'directory'
FILE = 'file'


class BrowserNode(lefttree.Node):
    def __init__(self, *args, contents):
        super().__init__(*args, icon='folder-symbolic', children=Gio.ListStore() if DIRECTORY in contents else None, item_type=_item.SongItem)
        self.contents = contents


class BrowserWidget(lefttree.WidgetWithPanedTreeList):
    def __init__(self, fields, config, tree):
        main = ViewWithCopy(fields=fields, sortable=True)
        super().__init__(main, config, tree)

        self.connect_clean(tree.root.children, 'items-changed', self.root_items_changed_cb)
        if len(self.left_selection_model) > 0:
            self.left_selection_model[0].set_expanded(True)
        self.add_cleanup_below(main)

    def root_items_changed_cb(self, model, p, r, a):
        if a:
            self.left_selection_model[0].set_expanded(True)


class BrowserTree(lefttree.Tree):
    def __init__(self, ampd):
        super().__init__()
        self.ampd = ampd

    @staticmethod
    def get_root():
        return BrowserNode(contents={DIRECTORY: [{DIRECTORY: ''}]})

    @misc.create_task
    async def fill_node(self, node):
        contents = {os.path.basename(item[DIRECTORY]) or _("Music"): await self.ampd.lsinfo(item[DIRECTORY]) for item in node.contents.get(DIRECTORY, [])}
        if node.children is not None:
            expanded = any(row.get_expanded() for row in node.rows)
            self.merge(node.children, sorted(contents), expanded, lambda name: BrowserNode(name, node.path, contents=contents[name]), lambda node: self.update_node(node, contents))
        songs = node.contents.get(FILE, [])
        misc.songs_set_fields(songs)
        node.item_model.set_values(songs)

    @staticmethod
    def update_node(node, contents):
        node.contents = contents[node.name]


class __unit__(mixins.UnitConfigMixin, mixins.UnitComponentQueueActionMixin, unit.Unit):
    TITLE = _("Database Browser")
    KEY = '2'

    def __init__(self, manager):
        super().__init__(manager, config.Dict(paned=BrowserWidget.get_paned_config()))

        self.require('database')
        self.require('song')
        self.require('persistent')

        self.tree = BrowserTree(self.ampd)

    def new_widget(self):
        browser = BrowserWidget(self.unit_song.fields, self.config['paned'], self.tree)
        view = browser.main

        view.add_context_menu_actions(self.generate_foreign_queue_actions(view), 'foreign-queue', self.TITLE, protect=self.unit_persistent.protect, prepend=True)
        browser.add_context_menu_actions(self.generate_foreign_queue_actions(view, False), 'foreign-queue', self.TITLE, protect=self.unit_persistent.protect, prepend=True)
        browser.connect_clean(view.item_view, 'activate', self.view_activate_cb)

        return browser

    @ampd.task
    async def client_connected_cb(self, client):
        while True:
            self.tree.start()
            await self.ampd.idle(ampd.DATABASE)
