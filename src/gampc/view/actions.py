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

from ..util import action
from ..util import item
from ..util import misc

from ..ui import contextmenu
from ..ui import dialog
from ..ui import dnd

from .base import ViewBase


class ViewWithContextMenu(contextmenu.ContextMenuActionMixin, ViewBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_context_menu_actions(self.generate_filter_actions(), 'filter', _("Filter actions"))

    def generate_filter_actions(self):
        if self.filterable:
            yield action.PropertyActionInfo('filtering', self, _("Filter view"), ['<Control><Shift>f'])
            yield action.ActionInfo('filter-reset', self.action_filtering_reset_cb, _("Reset filter and order") if self.sortable else _("Reset filter"), ['<Control><Shift>r'])

    def action_filtering_reset_cb(self, action, parameter):
        if self.filtering:
            self.filtering = False
        self.filter_item.load({})
        if self.sortable:
            self.item_view.sort_by_column(None, Gtk.SortType.ASCENDING)


class ViewWithCopy(ViewWithContextMenu):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.add_context_menu_actions(self.generate_editing_actions(), 'view-edit', _("Edit"))

        self.drag_source = dnd.ListDragSource(self.content_from_items, self.remove_positions, self.lock, self.unlock)
        self.item_view.rows.add_controller(self.drag_source)

    def cleanup(self):
        self.item_view.rows.remove_controller(self.drag_source)
        del self.drag_source
        super().cleanup()

    def generate_editing_actions(self):
        yield action.ActionInfo('copy', self.action_copy_cb, _("Copy"), ['<Control>c'])

    def action_copy_cb(self, action, parameter):
        self.copy_items(self.get_items(self.get_selection()))

    def copy_items(self, items):
        self.get_clipboard().set_content(self.content_from_items(items))

    remove_positions = NotImplemented

    @staticmethod
    def lock():
        pass

    @staticmethod
    def unlock():
        pass

    transfer_type = NotImplemented
    extra_transfer_types = NotImplemented

    @classmethod
    def content_from_items(cls, items):
        return item.transfer_union(items, cls.transfer_type, *cls.extra_transfer_types)


class ViewWithCopyPaste(ViewWithCopy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, sortable=False, **kwargs)

        self.connect('notify::filtering', self.check_editable)

        self.drop_target = dnd.ListDropTarget(Gdk.ContentFormats.new_for_gtype(self.transfer_type), self.add_items)
        self.item_view.rows.add_controller(self.drop_target)

        self.set_editable(True)

    def cleanup(self):
        self.disconnect_by_func(self.check_editable)
        self.item_view.rows.remove_controller(self.drop_target)
        del self.drop_target
        super().cleanup()

    def get_editable(self):
        return self._editable

    def set_editable(self, editable):
        self._editable = editable
        self.check_editable()

    def check_editable(self, *args):
        editable = self._editable and not self.filtering
        actions = self.actions['view-edit']
        for name in actions.list_actions():
            if name != 'copy':
                actions.lookup_action(name).set_enabled(editable)
        self.drag_source.set_actions(Gdk.DragAction.COPY | Gdk.DragAction.MOVE if editable else Gdk.DragAction.COPY)

    def generate_editing_actions(self):
        cut = action.ActionInfo('cut', self.action_cut_cb, _("Cut"), ['<Control>x'], True, arg_format='b')
        yield cut
        yield from super().generate_editing_actions()
        paste_after = action.ActionInfo('paste', self.action_paste_cb, _("Paste after"), ['<Control>v'], True, arg_format='b')
        yield paste_after
        yield paste_after.derive(_("Paste before"), ['<Control>b'], False)
        yield cut.derive(_("Delete"), ['Delete'], False)

    def action_cut_cb(self, action, parameter):
        selection = self.get_selection()
        if not selection:
            return
        if parameter.unpack():
            self.copy_items(self.get_items(selection))
        pos = selection[0]
        if pos > 0 and pos + len(selection) >= self.item_selection_model.get_n_items():
            pos -= 1
        self.remove_positions(selection)
        self.item_selection_model.select_item(pos, True)

    def action_paste_cb(self, action, parameter):
        row = self.item_view.rows.get_focus_child()
        if row is None:
            return
        pos = row.get_first_child().get_first_child().pos
        if parameter.unpack():
            pos += 1
        self.get_clipboard().read_value_async(self.transfer_type, 0, None, self.action_paste_finish_cb, pos)

    def action_paste_finish_cb(self, clipboard, result, pos):
        values = clipboard.read_value_finish(result).values
        if values is not None:
            self.add_items(values, pos)

    def generate_url_actions(self):
        yield action.ActionInfo('add-url', self.action_add_url_cb, _("Add URL or filename"))

    @misc.create_task
    async def action_add_url_cb(self, action, parameter):
        selection = self.get_selection()
        if selection:
            pos = selection[0]
        else:
            return
        dialog_ = dialog.TextDialogAsync(transient_for=self.get_root(), decorated=False, text='http://')
        url = await dialog_.run()
        if url:
            item_ = item.Item(value=dict(file=url))
            transfer = self.transfer_type([item_])
            self.add_items(transfer.values, pos)

    add_items = remove_positions = NotImplemented
