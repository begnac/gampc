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

from ..util import misc
from ..util import tree
from ..util import unit

from ..view.cache import ViewCacheWithCopy

from ..control import compound

from . import mixins


DIRECTORY = 'directory'


class BrowserWidget(compound.WidgetWithPanedTreeList):
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


class BrowserTree(tree.Tree):
    def __init__(self, ampd, update_cache):
        super().__init__()
        self.ampd = ampd
        self.update_cache = update_cache

    @staticmethod
    def get_root():
        return tree.Node(contents={DIRECTORY: [{DIRECTORY: _("Music")}]})

    @misc.create_task
    async def fill_node(self, node):
        for folder in sorted(os.path.basename(item[DIRECTORY]) for item in node.contents.get(DIRECTORY, [])):
            path = node.path + [folder]
            contents = await self.ampd.lsinfo('/'.join(path[1:]))
            self.update_cache(contents.get('file', []))
            node.model.append(tree.Node(name=folder, path=node.path, icon='folder-symbolic', contents=contents, leaf=DIRECTORY not in contents))
        node.keys = [item['file'] for item in node.contents.get('file', [])]


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

    def cleanup(self):
        del self.tree
        super().cleanup()

    def new_widget(self):
        browser = BrowserWidget(self.unit_fields.fields, self.unit_database.cache, self.config.pane_separator, self.tree)
        view = browser.main

        view.add_context_menu_actions(self.generate_queue_actions(view), 'queue', self.TITLE, protect=self.unit_persistent.protect)
        browser.add_context_menu_actions(self.generate_queue_actions(view, False), 'queue', self.TITLE, protect=self.unit_persistent.protect)
        browser.connect_clean(view.item_view, 'activate', self.view_activate_cb)

        return browser

    @ampd.task
    async def client_connected_cb(self, client):
        while True:
            self.tree.start()
            await self.ampd.idle(ampd.DATABASE)
