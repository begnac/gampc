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


import ampd

from . import component


class ItemList(component.Component):
    duplicate_test_columns = []
    duplicate_extra_items = None

    def __init__(self, unit, view, *args, **kwargs):
        super().__init__(unit, *args, **kwargs)

        self.view = view
        self.view.item_view.add_css_class('itemlist')

        self.connect_clean(self.view.item_view, 'activate', self.view_activate_cb)
        if self.duplicate_test_columns:
            self.connect_clean(self.view.item_store, 'items-changed', self.mark_duplicates)

        # self.itemlist_actions = self.add_actions_provider('itemlist')
        # self.itemlist_actions.add_action(util.resource.Action('reset', self.action_reset_cb))
        # self.itemlist_actions.add_action(util.resource.Action('copy', self.action_copy_delete_cb))

    def cleanup(self):
        self.widget.cleanup()
        super().cleanup()
        del self.view

    @ampd.task
    async def view_activate_cb(self, view, position):
        if self.unit.unit_persistent.protect_active:
            return
        filename = self.view.item_selection_model[position].get_key()
        items = await self.ampd.playlistfind('file', filename)
        if items:
            item_id = sorted(items, key=lambda item: item['Pos'])[0]['Id']
        else:
            item_id = await self.ampd.addid(filename)
        await self.ampd.playid(item_id)

    def mark_duplicates(self, *args):
        items = list(self.view.item_store)
        if self.duplicate_extra_items:
            items += list(self.duplicate_extra_items)

        marker = 0
        firsts = {}
        for i, item_ in enumerate(items):
            if item_.get_key() == self.unit.unit_database.SEPARATOR_FILE:
                continue
            test = tuple(item_.get_field(name) for name in self.duplicate_test_columns)
            first = firsts.get(test)
            if first is None:
                firsts[test] = i
                if item_.duplicate is not None:
                    item_.duplicate = None
            else:
                if items[first].duplicate is None:
                    items[first].duplicate = marker
                    marker += 1
                item_.duplicate = items[first].duplicate
