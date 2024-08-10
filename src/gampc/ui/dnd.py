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

from .. import util


class ListDragSource(Gtk.DragSource):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        icon = Gtk.IconTheme.get_for_display(util.misc.get_display()).lookup_icon('view-list-symbolic', None, 48, 1, 0, 0)
        self.set_icon(icon, 5, 5)
        self.connect('prepare', self.drag_prepare_cb)
        # self.connect('drag-begin', self.drag_begin_cb)
        # self.connect('drag-cancel', self.drag_cancel_cb)
        self.connect('drag-end', self.drag_end_cb)

    @staticmethod
    def prepare_cb(self, source, x, y, get_selection):
        source.selection = get_selection()
        if not source.selection:
            row, x, y = util.misc.find_descendant_at_xy(self.get_widget(), x, y, 1)
            if row is not None:
                source.selection = [row.pos]
            else:
                source.selection = None
                return None
        return self.content_from_items(self.view.item_selection[pos] for pos in source.selection)

    # def drag_begin_cb(self, source, drag):
    #     pass

    # def drag_cancel_cb(self, source, drag, reason):
    #     return False

    def end_cb(self, source, drag, delete):
        print('end', source, delete)
        if delete:
            self.remove_items([self.view.item_selection[pos] for pos in source.selection])
        del source.selection


class ListDropTarget(Gtk.DropTarget):
    def __init__(self, add_items):
        super().__init__(actions=Gdk.DragAction.COPY | Gdk.DragAction.MOVE, formats=Gdk.ContentFormats.new_for_gtype(util.item.ItemsFromCacheTransfer))
        self.row = None
        self.connect('enter', self.action_cb)
        self.connect('motion', self.action_cb)
        self.connect('leave', self.leave_cb)
        self.connect('drop', self.drop_cb, add_items)

    # def cleanup(self):
    #     self.disconnect_by_func(self.drop_cb)

    def actions(self):
        state = util.misc.get_modifier_state()
        if state & Gdk.ModifierType.ALT_MASK:
            return 0
        if self.get_actions() & Gdk.DragAction.MOVE and state & Gdk.ModifierType.SHIFT_MASK:
            return Gdk.DragAction.MOVE
        else:
            return Gdk.DragAction.COPY

    def drop_cleanup(self):
        if self.row is not None:
            self.row.remove_css_class('drop-row')
            self.row = None

    @staticmethod
    def action_cb(self, x, y):
        row, x, y = util.misc.find_descendant_at_xy(self.get_widget(), x, y, 1)
        if row is None:
            row = self.get_widget().get_last_child()
        elif y < row.get_height() / 2:
            if row.pos == 0:
                row = None
            else:
                row = self.get_widget().observe_children()[row.pos - 1]
        if row != self.row:
            if self.row is not None:
                self.row.remove_css_class('drop-row')
            self.row = row
            if self.row is not None:
                self.row.add_css_class('drop-row')

        return self.actions()

    @staticmethod
    def leave_cb(self):
        print('leave')
        self.drop_cleanup()

    @staticmethod
    def drop_cb(self, value, x, y, add_items):
        add_items(value.values, self.row.pos + 1 if self.row is not None else 0)
        self.drop_cleanup()
