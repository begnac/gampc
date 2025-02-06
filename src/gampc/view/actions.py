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

        self.drag_source = Gtk.DragSource(actions=Gdk.DragAction.COPY)
        icon = Gtk.IconTheme.get_for_display(misc.get_display()).lookup_icon('view-list-symbolic', None, 48, 1, 0, 0)
        self.drag_source.set_icon(icon, 5, 5)
        self.connect_clean(self.drag_source, 'prepare', self.drag_prepare_cb)
        # self.drag_source.connect('drag-begin', self.drag_begin_cb)
        # self.drag_source.connect('drag-cancel', self.drag_cancel_cb)
        self.connect_clean(self.drag_source, 'drag-end', self.drag_end_cb)
        self.item_view.rows.add_controller(self.drag_source)

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

    def drag_prepare_cb(self, drag_source, x, y):
        row, x, y = misc.find_descendant_at_xy(self.item_view.rows, x, y, 1)
        if row is None:
            return

        self.drag_selection = self.get_selection()
        pos = row.get_first_child().get_first_child().pos
        if pos not in self.drag_selection:
            self.item_selection_model.select_item(pos, True)
            self.drag_selection = [pos]
        self.lock()
        return self.content_from_items(self.item_selection_filter_model)

    # def drag_begin_cb(self, source, drag):
    #     pass

    # def drag_cancel_cb(self, source, drag, reason):
    #     return False

    def drag_end_cb(self, drag_source, drag, delete):
        if delete:
            self.remove_positions(self.drag_selection)
        self.unlock()
        del self.drag_selection


class ViewWithCopyPaste(ViewWithCopy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, sortable=False, **kwargs)

        self.drop_target = Gtk.DropTarget(actions=Gdk.DragAction.COPY | Gdk.DragAction.MOVE, formats=Gdk.ContentFormats.new_for_gtype(self.transfer_type))
        self.connect_clean(self.drop_target, 'enter', self.drop_action_cb)
        self.connect_clean(self.drop_target, 'motion', self.drop_action_cb)
        # self.connect_clean(self.drop_target, 'leave', self.drop_leave_cb)
        self.connect_clean(self.drop_target, 'drop', self.drop_cb)
        self.item_view.rows.add_controller(self.drop_target)
        self.drop_row = None

        self.set_editable(True)

    def get_editable(self):
        return self._editable

    def set_editable(self, editable):
        self._editable = editable
        self.check_editable()

    def check_editable(self):
        editable = self._editable and not self.filtering
        actions = self.actions['view-edit']
        for name in actions.list_actions():
            if name != 'copy':
                actions.lookup_action(name).set_enabled(editable)
        self.drag_source.set_actions(Gdk.DragAction.COPY | Gdk.DragAction.MOVE if editable else Gdk.DragAction.COPY)

    def notify_filtering_cb(self, param):
        super().notify_filtering_cb(param)
        self.check_editable()

    def generate_editing_actions(self):
        cut = action.ActionInfo('cut', self.action_cut_cb, _("Cut"), ['<Control>x'], True, arg_format='b')
        yield cut
        yield from super().generate_editing_actions()
        paste = action.ActionInfo('paste', self.action_paste_cb, _("Paste"), ['<Control>v'], False, arg_format='b')
        yield paste
        yield paste.derive(_("Paste after"), ['<Control><Shift>v'], True)
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
        after = parameter.unpack()
        row = self.item_view.rows.get_focus_child()
        if row is None:
            if after:
                return
            else:
                pos = self.item_model.get_n_items()
        else:
            pos = row.get_first_child().get_first_child().pos
            if after:
                pos += 1
        self.get_clipboard().read_value_async(self.transfer_type, 0, None, self.action_paste_finish_cb, pos)

    def action_paste_finish_cb(self, clipboard, result, pos):
        values = clipboard.read_value_finish(result).values
        if values is not None:
            self.add_items(pos, values)

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
            self.add_items(pos, transfer.values)

    def set_drop_row(self, drop_row=None):
        if drop_row != self.drop_row:
            if self.drop_row is not None:
                self.drop_row.remove_css_class('drop-row')
            self.drop_row = drop_row
            if self.drop_row is not None:
                self.drop_row.add_css_class('drop-row')

    def drop_action_cb(self, drop_target, x, y):
        row, x, y = misc.find_descendant_at_xy(self.item_view.rows, x, y, 1)
        if row is None:
            row = self.item_view.rows.get_last_child()
        elif y < row.get_height() / 2:
            row = row.get_prev_sibling()
        self.set_drop_row(row)
        return Gdk.DragAction.MOVE

    # def drop_leave_cb(self, drop_target):
    #     # print('leave')
    #     self.set_row()

    def drop_cb(self, drop_target, value, x, y):
        pos = self.drop_row.get_first_child().get_first_child().pos + 1 if self.drop_row is not None else 0
        self.add_items(pos, value.values)
        return True

    add_items = remove_positions = NotImplemented
