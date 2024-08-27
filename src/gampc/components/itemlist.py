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

import ampd

from ..util import item

from ..ui import view

from . import component


class ItemList(component.Component):
    duplicate_test_columns = []
    duplicate_extra_items = None

    factory_factory = view.LabelItemFactory
    item_factory = item.Item
    widget_factory = view.ViewWithCopy

    def __init__(self, unit, *args, **kwargs):
        super().__init__(unit, *args, **kwargs)

        self.widget = self.view = self.widget_factory(self.get_fields(), self.factory_factory, self.item_factory)
        self.view.item_view.add_css_class('itemlist')
        self.focus_widget = self.view.item_view

        self.signal_handler_connect(self.view.item_view, 'activate', self.view_activate_cb)
        if self.duplicate_test_columns:
            self.signal_handler_connect(self.view.item_store, 'items-changed', self.mark_duplicates)

        # self.itemlist_actions = self.add_actions_provider('itemlist')
        # self.itemlist_actions.add_action(util.resource.Action('reset', self.action_reset_cb))
        # self.itemlist_actions.add_action(util.resource.Action('copy', self.action_copy_delete_cb))

    def shutdown(self):
        self.view.cleanup()
        super().shutdown()
        del self.view
        del self.widget

    # def bind_cb(self, factory, listitem):
    #     listitem.row = listitem.get_child().get_parent().get_parent()
    #     listitem.row.pos = listitem.get_position()

    @ampd.task
    async def view_activate_cb(self, view, position):
        if self.unit.unit_persistent.protect_active:
            return
        filename = self.view.item_store_selection[position].get_key()
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

    # def action_reset_cb(self, action, parameter):
    #     self.view.filter_item.set_data({})
    #     self.view.filtering = False
    #     if self.sortable:
    #         self.view.item_view.sort_by_column(None, Gtk.SortType.ASCENDING)


class ItemListEditStackMixin:
    pass
    # @ampd.task
    # async def action_reset_cb(self, action, parameter):
    #     if not self.edit_stack or not self.edit_stack.deltas:
    #         return
    #     if not await dialog.MessageDialogAsync(transient_for=self.widget.get_root(), message=_("Reset and lose all modifications?")).run():
    #         return
    #     self.edit_stack.undo()
    #     self.edit_stack.reset()
    #     self.edit_stack_changed()


class ItemListTreeListMixin(component.ComponentPaneTreeMixin):
    def __init__(self, unit, **kwargs):
        self.left_store = Gtk.TreeListModel.new(unit.root.model, False, False, lambda node: node.expose())
        self.left_selection = Gtk.MultiSelection(model=self.left_store)

        super().__init__(unit, **kwargs)

        self.signal_handler_connect(self.left_view, 'activate', self.left_view_activate_cb)
        self.left_selection.select_item(0, True)

    @staticmethod
    def left_view_activate_cb(view, position):
        row = view.get_model()[position]
        if row.is_expandable():
            row.set_expanded(not row.get_expanded())
