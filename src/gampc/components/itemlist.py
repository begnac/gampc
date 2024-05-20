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


from gi.repository import GLib
from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import Gtk

import asyncio
import ast

import ampd

from .. import util
from .. import ui
from . import component



TRY_DND = False


class ItemList(component.Component):
    sortable = True

    duplicate_test_columns = []
    duplicate_extra_items = None

    def __init__(self, unit, widget_factory, *args, **kwargs):
        super().__init__(unit, *args, **kwargs)

        self.widget = self.view = ui.view.View(self.fields, widget_factory, util.item.ItemListStore(self.item_factory), self.__class__.sortable, unit_misc=unit.unit_misc)
        self.view.item_view.add_css_class('itemlist')
        self.focus_widget = self.view.item_view

        self.itemlist_actions = self.add_actions_provider('itemlist')
        self.itemlist_actions.add_action(util.resource.Action('reset', self.action_reset_cb))
        self.itemlist_actions.add_action(util.resource.Action('copy', self.action_copy_delete_cb))

        if TRY_DND:
            self.setup_drag()

        self.itemlist_actions.add_action(Gio.PropertyAction(name='filter', object=self.view, property_name='filtering'))

        self.setup_context_menu(f'{self.name}.context', self.view)
        self.signal_handler_connect(self.view.item_view, 'activate', self.view_activate_cb)
        if self.duplicate_test_columns:
            self.signal_handler_connect(self.view.item_store, 'items-changed', self.mark_duplicates)

    def shutdown(self):
        del self.itemlist_actions
        self.view.cleanup()
        super().shutdown()

    @staticmethod
    def content_from_items(items):
        return Gdk.ContentProvider.new_for_value(repr([item.to_string() for item in items]))

    @staticmethod
    def strings_from_raw(raw):
        try:
            strings = ast.literal_eval(raw)
            if isinstance(strings, list) and all(isinstance(string, str) for string in strings):
                return strings
        except Exception:
            pass

    @ampd.task
    async def view_activate_cb(self, view, position):
        if self.unit.unit_persistent.protect_active:
            return
        filename = self.view.item_selection[position].get_name()
        items = await self.ampd.playlistfind('file', filename)
        if items:
            item_id = sorted(items, key=lambda item: item['Pos'])[0]['Id']
        else:
            item_id = await self.ampd.addid(filename)
        await self.ampd.playid(item_id)

    def set_items(self, items):
        self.splice_items(0, None, items)

    def splice_items(self, pos, remove, add):
        if remove is None:
            remove = self.view.item_store.get_n_items()
        self.view.item_store.splice_items(pos, remove, add)

    def mark_duplicates(self, *args):
        items = list(self.view.item_store)
        if self.duplicate_extra_items:
            items += list(self.duplicate_extra_items)

        marker = 0
        firsts = {}
        for i, item in enumerate(items):
            if item.value == self.unit.unit_server.SEPARATOR_FILE:  # Only place where self is used here ...
                continue
            test = tuple(item.data.get(name) for name in self.duplicate_test_columns)
            first = firsts.get(test)
            if first is None:
                firsts[test] = i
                if item.duplicate is not None:
                    item.duplicate = None
                    item.rebind()
            else:
                if items[first].duplicate is None:
                    items[first].duplicate = marker
                    items[first].rebind()
                    marker += 1
                item.duplicate = items[first].duplicate
                item.rebind()

    def action_reset_cb(self, action, parameter):
        self.view.filter_item.set_data({})
        self.view.filtering = False
        if self.sortable:
            self.view.item_view.sort_by_column(None, Gtk.SortType.ASCENDING)

    def action_copy_delete_cb(self, action, parameter):
        items = self.view.get_selection_items()
        if action.get_name() in ['copy', 'cut']:
            self.widget.get_clipboard().set_content(self.content_from_items(items))
        if action.get_name() in ['delete', 'cut']:
            self.remove_items(items)

    @staticmethod
    def row_get_position(row, *, after=False):
        pos = row.get_first_child()._pos
        if after:
            pos += 1
        return pos

    # def drag_begin_cb(self, source, drag):
    #     positions = self.get_selection()
    #     if not positions:
    #         return
    #     icons = [self.create_row_drag_icon(ref.get_path()) for ref in context.drag_refs]
    #     xscale, yscale = icons[0].get_device_scale()
    #     width, height = icons[0].get_width(), icons[0].get_height() - yscale
    #     target = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(width / xscale), int(height * len(context.drag_refs) / yscale) + 1)
    #     cr = cairo.Context(target)
    #     cr.set_source_rgba(0, 0, 0, 1)
    #     cr.paint()
    #     y = 2
    #     for icon in icons:
    #         cr.set_source_surface(icon, 2 / xscale, y / yscale)
    #         cr.paint()
    #         y += height
    #     icon.flush()
    #     Gtk.drag_set_icon_surface(context, target)

    def setup_drag(self):
        self.drag_source = Gtk.DragSource(actions=Gdk.DragAction.COPY)
        self.drag_source.set_icon(Gtk.IconTheme.get_for_display(util.misc.get_display()).lookup_icon('face-cool', None, 48, 1, Gtk.TextDirection.NONE, 0), 5, 5)
        self.signal_handler_connect(self.drag_source, 'prepare', self.drag_prepare_cb)
        self.signal_handler_connect(self.drag_source, 'drag-begin', self.drag_begin_cb)
        self.signal_handler_connect(self.drag_source, 'drag-cancel', self.drag_cancel_cb)
        self.signal_handler_connect(self.drag_source, 'drag-end', self.drag_end_cb)
        self.view.item_view_rows.add_controller(self.drag_source)

        self.drag_key_controller = Gtk.EventControllerKey()
        self.signal_handler_connect(self.drag_key_controller, 'key-pressed', self.drag_key_pressed_cb, self.drag_source)
        self.view.item_view_rows.add_controller(self.drag_key_controller)

    def drag_prepare_cb(self, source, x, y):
        source.items = self.view.get_selection_items()
        if not source.items:
            row, x, y = util.misc.find_descendant_at_xy(self.view.item_view_rows, x, y, 1)
            if row is not None:
                source.items = [self.view.item_selection[row.get_first_child()._pos]]
            else:
                return None
        source.set_content(self.content_from_items(source.items))
        return self.content_from_items(source.items)

    def drag_begin_cb(self, source, drag):
        print(drag.get_actions())
        print(drag.set_property('actions', Gdk.DragAction.COPY))
        print(drag.get_actions())
        pass

    def drag_cancel_cb(self, source, drag, reason):
        print(2, source.get_content(), drag, reason)
        source.set_content(None)
        drag.drop_done(False)
        return False

    def drag_end_cb(self, source, drag, delete):
        if delete:
            self.remove_items(source.items)
        del source.items

    @staticmethod
    def drag_key_pressed_cb(controller, keyval, keycode, modifiers, source):
        if keyval == Gdk.KEY_Escape:
            source.drag_cancel()
        return False


class AIOQueue:
    def __init__(self):
        self.task = None

    def queue_task_lazy(self, coro, *args, **kwargs):
        self.task = asyncio.create_task(self.wrapper_lazy(self.task, coro(self.task, *args, **kwargs)))
        self.task.add_done_callback(self.task_done)

    @staticmethod
    async def wrapper_lazy(task, awaitable):
        await awaitable
        if task is not None:
            await task

    def task_done(self, task):
        if task == self.task:
            self.task = None


class ItemListFromCacheMixin:
    def __init__(self, unit, *args, **kwargs):
        super().__init__(unit, *args, **kwargs)
        self.aioqueue = AIOQueue()

    def splice_items(self, pos, remove, add):
        self.aioqueue.queue_task_lazy(self._splice_items, pos, remove, list(add))

    async def _splice_items(self, task, pos, remove, add):
        await self.unit.database.ensure(add)
        if task is not None:
            await task
        super().splice_items(pos, remove, add)

    def item_factory(self):
        return util.item.ItemFromCache(self.unit.database)


class ItemListEditableMixin:
    sortable = False

    def __init__(self, unit, *args, editable=True, **kwargs):
        super().__init__(unit, *args, **kwargs)
        self._editable = editable

        self.itemlist_actions.add_action(util.resource.Action('paste', self.action_paste_cb))
        self.itemlist_actions.add_action(util.resource.Action('paste-before', self.action_paste_cb))
        self.itemlist_actions.add_action(util.resource.Action('delete', self.action_copy_delete_cb))
        self.itemlist_actions.add_action(util.resource.Action('cut', self.action_copy_delete_cb))
        self.signal_handler_connect(self.view, 'notify::filtering', self.check_editable)

        # self.setup_drop()

    def get_editable(self):
        return self._editable

    def set_editable(self, editable):
        self._editable = editable
        self.check_editable()

    def check_editable(self, *args):
        editable = self._editable and not self.view.filtering
        for name in ['paste', 'paste-before', 'delete', 'cut']:
            self.itemlist_actions.lookup(name).set_enabled(editable)
        if TRY_DND:
            self.drag_source.set_actions(Gdk.DragAction.COPY | Gdk.DragAction.MOVE if editable else Gdk.DragAction.COPY)

    def action_paste_cb(self, action, parameter):
        self.widget.get_clipboard().read_text_async(None, self.action_paste_finish_cb, action.get_name().endswith('-before'))

    def action_paste_finish_cb(self, clipboard, result, before):
        try:
            strings = self.strings_from_raw(clipboard.read_text_finish(result))
        except GLib.GError as error:
            print(error)
            return
        row = self.view.item_view_rows.get_focus_child()
        if strings is not None and row is not None:
            self.add_items(strings, self.row_get_position(row, after=not before))

    def setup_drop(self):
        self.drop_target = Gtk.DropTarget(actions=Gdk.DragAction.COPY | Gdk.DragAction.MOVE, formats=Gdk.ContentFormats.parse('gchararray'))
        self.signal_handler_connect(self.drop_target, 'enter', self.drop_action_cb)
        self.signal_handler_connect(self.drop_target, 'motion', self.drop_action_cb)
        self.signal_handler_connect(self.drop_target, 'drop', self.drop_cb)
        # self.signal_handler_connect(self.drop_target, 'notify::value', misc.AutoWeakMethod(self.drop_notify_value_cb))
        # self.drop_target.set_preload(True)
        self.view.item_view_rows.add_controller(self.drop_target)

        self.drop_key_controller = Gtk.EventControllerKey()
        self.signal_handler_connect(self.drop_key_controller, 'key-pressed', self.drop_key_pressed_cb, self.drop_target)
        self.signal_handler_connect(self.drop_key_controller, 'modifiers', self.drop_modifiers_cb, self.drop_target)
        self.view.item_view_rows.add_controller(self.drop_key_controller)

    def drop_action_cb(self, target, x, y):
        row, x, y = util.misc.find_descendant_at_xy(target.get_widget(), x, y, 1)
        if row is None:
            return 0
        if target.get_value() is not None and not target.get_value().is_of_type(GLib.VariantType('as')):
            return 0
        if target.get_actions() & Gdk.DragAction.MOVE and util.misc.get_modifier_state() & Gdk.ModifierType.SHIFT_MASK:
            return Gdk.DragAction.MOVE
        else:
            return Gdk.DragAction.COPY

    def drop_cb(self, target, value, x, y):
        data = self.data_from_raw(value)
        if data is None:
            return
        row, x, y = util.misc.find_descendant_at_xy(self.view.item_view_rows, x, y, 1)
        if row is not None:
            if y < row.get_allocation().height / 2:
                before = True
            else:
                before = False
            self.add_items(data, self.row_get_position(row, after=not before))

    # def drop_notify_value_cb(self, target, param):
    #     drop = target.get_current_drop()
    #     if drop is None:
    #         return
    #     if not target.get_value().is_of_type(GLib.VariantType('as')):
    #         target.reject()

    @staticmethod
    def drop_key_pressed_cb(controller, keyval, keycode, modifiers, target):
        if keyval == Gdk.KEY_Escape:
            target.get_drop().finish(0)
            target.reject()
        return False

    @staticmethod
    def drop_modifiers_cb(controller, modifiers, target):
        if target.get_actions() & Gdk.DragAction.MOVE and util.misc.get_modifier_state() & Gdk.ModifierType.SHIFT_MASK:
            pass


class ItemListEditStackMixin(ItemListEditableMixin):
    def __init__(self, unit, *args, **kwargs):
        super().__init__(unit, *args, **kwargs)
        self.itemlist_actions.add_action(util.resource.Action('save', self.action_save_cb))
        # self.itemlist_actions.add_action(util.resource.Action('reset', self.action_reset_cb))
        self.itemlist_actions.add_action(util.resource.Action('undo', self.action_do_cb))
        self.itemlist_actions.add_action(util.resource.Action('redo', self.action_do_cb))

        self.edit_stack = None

        # self.view.item_edited_hooks.append(self.item_edited_hook)

    def shutdown(self):
        super().shutdown()
        del self.edit_stack
    #     self.view.item_edited_hooks.remove(self.item_edited_hook)

    # def item_edited_hook(self, item, key, item):
    #     new_item = util.item.Item(item.get_data())
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
            self.edit_stack.set_splicer(self.splice_items)
        else:
            self.view.item_store.remove_all()

    def step_edit_stack(self, push):
        focus, selection = self.edit_stack.step(push)
        self.refocus(focus, selection)

    def refocus(self, focus, selection):
        if focus is not None:
            self.view.item_view.scroll_to(focus, None, Gtk.ListScrollFlags.FOCUS, None)
        if selection is not None:
            self.view.item_selection.unselect_all()
            for pos in selection:
                self.view.item_selection.select_item(pos, False)
        self.edit_stack_changed()

    def remove_items(self, items):
        if not items:
            return
        indices = []
        for i, item in enumerate(self.view.item_selection):
            if item in items:
                indices.append(i)
                items.remove(item)
        if items:
            raise RuntimeError
        deltas = []
        i = j = indices[0]
        for k in indices[1:] + [0]:
            j += 1
            if j != k:
                items = [item.get_value() for item in self.view.item_selection[i:j]]
                deltas.append(util.editstack.SimpleDelta(items, i, True))
                i = j = k
        self.edit_stack.set_from_here([util.editstack.MetaDelta(deltas, False)])
        self.step_edit_stack(True)

    def add_items(self, items, position):
        if not items:
            return
        self.edit_stack.set_from_here([util.editstack.SimpleDelta(items, position, True)])
        self.step_edit_stack(True)

    def edit_stack_changed(self):
        self.itemlist_actions.lookup_action('save').set_enabled(True)
        self.itemlist_actions.lookup_action('undo').set_enabled(self.edit_stack and self.edit_stack.pos > 0)
        self.itemlist_actions.lookup_action('redo').set_enabled(self.edit_stack and self.edit_stack.pos < len(self.edit_stack.deltas))

    def action_do_cb(self, action, parameter):
        if action.get_name() == 'redo':
            self.step_edit_stack(True)
        elif action.get_name() == 'undo':
            self.step_edit_stack(False)
        else:
            raise RuntimeError
        self.edit_stack_changed()

    @ampd.task
    async def action_reset_cb(self, action, parameter):
        if not self.edit_stack or not self.edit_stack.deltas:
            return
        if not await ui.dialog.AsyncMessageDialog(transient_for=self.widget.get_root(), message=_("Reset and lose all modifications?")).run():
            return
        self.edit_stack.undo()
        self.edit_stack.reset()
        self.edit_stack_changed()


class ItemListEditStackFromCacheMixin(ItemListEditStackMixin, ItemListFromCacheMixin):
    def refocus(self, focus, selection):
        self.aioqueue.queue_task_lazy(self._refocus, focus, selection)

    async def _refocus(self, task, *args):
        if task is not None:
            await task
        super().refocus(*args)


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


@util.unit.require_units('misc', 'itemlist')
class UnitItemListMixin(component.UnitComponentMixin):
    def __init__(self, *args, menus=[]):
        super().__init__(*args, menus=menus + ['context'])
