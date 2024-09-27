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


from gi.repository import Gio

import os

import ampd

from ..util import misc
from ..util import unit

from ..view.cache import ViewCacheWithCopy

from ..control import lefttree

from . import mixins


DIRECTORY = 'directory'
FILE = 'file'


class BrowserWidget(lefttree.WidgetWithPanedTreeList):
    def __init__(self, fields, cache, config, tree):
        main = ViewCacheWithCopy(fields=fields, cache=cache, sortable=True)
        super().__init__(main, config, tree)
        self.connect_clean(tree.root.model, 'items-changed', self.root_items_changed_cb)
        if len(self.left_selection) > 0:
            self.left_selection[0].set_expanded(True)
        self.add_cleanup_below(main)

    def root_items_changed_cb(self, model, p, r, a):
        if a:
            self.left_selection[0].set_expanded(True)

    def left_selection_changed_cb(self, selection, position, n_items):
        super().left_selection_changed_cb(selection, position, n_items)
        self.main.set_keys(sum((selection[pos].get_item().keys for pos in self.left_selection_pos), []))


class BrowserTree(lefttree.Tree):
    def __init__(self, ampd, update_cache):
        super().__init__()
        self.ampd = ampd
        self.update_cache = update_cache

    @staticmethod
    def get_root():
        return lefttree.Node(contents={DIRECTORY: [{DIRECTORY: ''}]}, expanded=True)

    @misc.create_task
    async def fill_node(self, node):
        contents = {os.path.basename(item[DIRECTORY]) or _("Music"): await self.ampd.lsinfo(item[DIRECTORY]) for item in node.contents.get(DIRECTORY, [])}
        if node.model is not None:
            self.merge(node.model, sorted(contents), node.expanded, lambda name: lefttree.Node(name, node.path, icon='folder-symbolic', contents=contents[name], model_factory=Gio.ListStore if DIRECTORY in contents[name] else None))
        self.update_cache(node.contents.get(FILE, []))
        node.keys = [item[FILE] for item in node.contents.get(FILE, [])]


class __unit__(mixins.UnitComponentQueueActionMixin, mixins.UnitConfigMixin, unit.Unit):
    TITLE = _("Database Browser")
    KEY = '2'

    def __init__(self, manager):
        super().__init__(manager)
        self.config.pane_separator._get(default=100)
        self.require('database')
        self.require('fields')
        self.require('persistent')

        self.tree = BrowserTree(self.ampd, self.unit_database.update)

    def new_widget(self):
        browser = BrowserWidget(self.unit_fields.fields, self.unit_database.cache, self.config.pane_separator, self.tree)
        view = browser.main

        view.add_context_menu_actions(self.generate_queue_actions(view), 'queue', self.TITLE, protect=self.unit_persistent.protect, prepend=True)
        browser.add_context_menu_actions(self.generate_queue_actions(view, False), 'queue', self.TITLE, protect=self.unit_persistent.protect, prepend=True)
        browser.connect_clean(view.item_view, 'activate', self.view_activate_cb)

        return browser

    @ampd.task
    async def client_connected_cb(self, client):
        while True:
            self.tree.start()
            await self.ampd.idle(ampd.DATABASE)
