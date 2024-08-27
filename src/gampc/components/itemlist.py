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


from gi.repository import Gdk
from gi.repository import Gtk

import asyncio

import ampd

from ..util import editstack
from ..util import item

from ..ui import dialog
from ..ui import view

from . import component


class ItemList(component.Component):
    sortable = True

    duplicate_test_columns = []
    duplicate_extra_items = None

    factory_factory = view.LabelItemFactory
    item_factory = item.Item

    def _get_widget(self):
        return view.ViewWithCopy(self.fields, self.factory_factory, interface=self.get_item_interface(), sortable=self.__class__.sortable)

    def __init__(self, unit, *args, **kwargs):
        super().__init__(unit, *args, **kwargs)

        self.widget = self.view = self._get_widget()
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

    def get_item_interface(self, content_formats=Gdk.ContentFormats.new_for_gtype(item.ItemKeyTransfer), **kwargs):
        return view.ItemViewInterface(content_from_items=self.content_from_items, content_formats=content_formats, **kwargs)

    @staticmethod
    def content_from_items(items):
        return item.transfer_union(items, item.ItemKeyTransfer, item.ItemStringTransfer)

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

    def set_values(self, values):
        self.splice_values(0, None, values)

    def splice_values(self, pos, remove, values):
        if remove is None:
            remove = self.view.item_store.get_n_items()
        values = list(values)
        n = len(values)
        new_items = [] if remove >= n else [self.item_factory() for _ in range(n - remove)]
        items = self.view.item_store[pos:pos + remove] + new_items
        for i in range(n):
            items[i].load(values[i])
        self.view.item_store[pos:pos + remove] = items[:n]

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

    def action_reset_cb(self, action, parameter):
        self.view.filter_item.set_data({})
        self.view.filtering = False
        if self.sortable:
            self.view.item_view.sort_by_column(None, Gtk.SortType.ASCENDING)

    def action_copy_delete_cb(self, action, parameter):
        items = self.view.get_selection_items()
        self.clipboard_content = self.content_from_items(items)
        if action.get_name() in ['copy', 'cut']:
            self.view.get_clipboard().set_content(self.clipboard_content)
        if action.get_name() in ['delete', 'cut']:
            self.remove_items(items)


class ItemListEditableMixin:
    def _get_widget(self):
        return view.ViewWithCopyPaste(self.fields, self.factory_factory, interface=self.get_item_interface())

    def get_item_interface(self):
        return super().get_item_interface(add_items=self.add_items, remove_items=self.remove_items)


class ItemListEditStackMixin(ItemListEditableMixin):
    def __init__(self, unit, *args, **kwargs):
        super().__init__(unit, *args, **kwargs)
        # self.itemlist_actions.add_action(util.resource.Action('save', self.action_save_cb))
        # self.itemlist_actions.add_action(util.resource.Action('reset', self.action_reset_cb))
        # self.itemlist_actions.add_action(util.resource.Action('undo', self.action_do_cb))
        # self.itemlist_actions.add_action(util.resource.Action('redo', self.action_do_cb))

        self.edit_stack = None

        # self.view.item_edited_hooks.append(self.item_edited_hook)

    def shutdown(self):
        super().shutdown()
        del self.edit_stack
    #     self.view.item_edited_hooks.remove(self.item_edited_hook)

    # def item_edited_hook(self, item, key, item):
    #     new_item = item.Item(item.get_data())
    #     if item:
    #         new_item[key] = item
    #     else:
    #         del new_item[key]
    #     position = list(self.view.item_selection).index(item)
    #     delta1 = SimpleDelta([item], position, False)
    #     delta2 = SimpleDelta([new_item], position, True)
    #     self.edit_stack.set_from_here([MetaDelta([delta1, delta2], True)])
    #     self.step_edit_stack(True)

    def set_edit_stack(self, edit_stack):
        if self.edit_stack is not None:
            self.edit_stack.set_splicer()
        self.edit_stack = edit_stack
        if edit_stack is not None:
            self.edit_stack.set_splicer(self.edit_stack_splicer)
        else:
            self.view.item_store.remove_all()

    def step_edit_stack(self, push):
        focus, selection = self.edit_stack.step(push)
        self.refocus(focus, selection)

    def refocus(self, focus, selection):
        if focus is not None:
            self.view.item_view.scroll_to(focus, None, Gtk.ListScrollFlags.FOCUS, None)
        if selection is not None:
            self.view.item_store_selection.unselect_all()
            for pos in selection:
                self.view.item_store_selection.select_item(pos, False)
        self.edit_stack_changed()

    def remove_items(self, items):
        if not items:
            return
        indices = []
        for i, item_ in enumerate(self.view.item_store_selection):
            if item_ in items:
                indices.append(i)
                items.remove(item_)
        if items:
            raise RuntimeError
        deltas = []
        i = j = indices[0]
        for k in indices[1:] + [0]:
            j += 1
            if j != k:
                values = [self.edit_stack_getter(item) for item in self.view.item_store_selection[i:j]]
                deltas.append(editstack.SimpleDelta(values, i, True))
                i = j = k
        self.edit_stack.set_from_here([editstack.MetaDelta(deltas, False)])
        self.step_edit_stack(True)

    def add_items(self, values, position):
        if not values:
            return
        self.edit_stack.set_from_here([editstack.SimpleDelta(values, position, True)])
        self.step_edit_stack(True)

    def edit_stack_changed(self):
        return
        # self.itemlist_actions.lookup_action('save').set_enabled(True)
        # self.itemlist_actions.lookup_action('undo').set_enabled(self.edit_stack and self.edit_stack.pos > 0)
        # self.itemlist_actions.lookup_action('redo').set_enabled(self.edit_stack and self.edit_stack.pos < len(self.edit_stack.deltas))

    def action_do_cb(self, action, parameter):
        if action.get_name() == 'redo':
            self.step_edit_stack(True)
        elif action.get_name() == 'undo':
            self.step_edit_stack(False)
        else:
            raise RuntimeError
        self.edit_stack_changed()

    #  REMOVE ASYNC !!!!!!!!!!!!
    @ampd.task
    async def action_reset_cb(self, action, parameter):
        if not self.edit_stack or not self.edit_stack.deltas:
            return
        if not await dialog.MessageDialogAsync(transient_for=self.widget.get_root(), message=_("Reset and lose all modifications?")).run():
            return
        self.edit_stack.undo()
        self.edit_stack.reset()
        self.edit_stack_changed()


class AIOQueue:
    def __init__(self):
        self.task = None

    def queue_task(self, func, *args, sync=False, **kwargs):
        wrapper = self.wrapper_sync if sync else self.wrapper_async
        self.task = asyncio.create_task(wrapper(self.task, func, *args, **kwargs))
        self.task.add_done_callback(self.task_done)

    @staticmethod
    async def wrapper_async(task, coro, *args, **kwargs):
        await coro(task, *args, **kwargs)
        if task is not None:
            await task

    @staticmethod
    async def wrapper_sync(task, func, *args, **kwargs):
        if task is not None:
            await task
        func(*args, **kwargs)

    def task_done(self, task):
        if task == self.task:
            self.task = None


class ItemListDatabaseMixin:
    def __init__(self, unit, *args, **kwargs):
        super().__init__(unit, *args, **kwargs)
        self.aioqueue = AIOQueue()

    def set_keys(self, keys):
        self.splice_keys(0, None, keys)

    def splice_keys(self, pos, remove, keys):
        self.aioqueue.queue_task(self._splice_keys, pos, remove, list(keys))

    async def _splice_keys(self, task, pos, remove, keys):
        await self.cache.ensure_keys(keys)
        if task is not None:
            await task
        self.splice_values(pos, remove, (self.cache[key] for key in keys))

    #  In case we inherit also from ItemListEditStackMixin.
    def refocus(self, *args):
        self.aioqueue.queue_task(super().refocus, *args, sync=True)


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
