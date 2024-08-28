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

from ..util import misc


CSS = '''
columnview > listview:drop(active) > row.drop-row {
  border-bottom-color: rgb(46,194,126);
}
'''


class ListDragSource(Gtk.DragSource):
    def __init__(self, content_from_items, remove_positions):
        super().__init__(actions=Gdk.DragAction.COPY)
        icon = Gtk.IconTheme.get_for_display(misc.get_display()).lookup_icon('view-list-symbolic', None, 48, 1, 0, 0)
        self.set_icon(icon, 5, 5)
        self.connect('prepare', self.prepare_cb, content_from_items)
        # self.connect('drag-begin', self.drag_begin_cb)
        # self.connect('drag-cancel', self.drag_cancel_cb)
        self.connect('drag-end', self.end_cb, remove_positions)

    @staticmethod
    def prepare_cb(self, x, y, content_from_items):
        widget = self.get_widget()
        row, x, y = misc.find_descendant_at_xy(widget, x, y, 1)
        if row is None:
            return

        model = widget.get_model()
        self.selection = list(misc.get_selection(model))
        pos = row.get_first_child().get_first_child().pos
        if pos not in self.selection:
            model.select_item(pos, True)
            self.selection = [pos]
        return content_from_items(model[pos] for pos in self.selection)

    # def drag_begin_cb(self, source, drag):
    #     pass

    # def drag_cancel_cb(self, source, drag, reason):
    #     return False

    @staticmethod
    def end_cb(self, drag, delete, remove_positions):
        if delete:
            remove_positions(self.selection)
        del self.selection


class ListDropTarget(Gtk.DropTarget):
    def __init__(self, content_formats, add_items):
        super().__init__(actions=Gdk.DragAction.COPY | Gdk.DragAction.MOVE, formats=content_formats)
        self.row = None
        self.connect('enter', self.action_cb)
        self.connect('motion', self.action_cb)
        # self.connect('leave', self.leave_cb)
        self.connect('drop', self.drop_cb, add_items)

    def set_row(self, row=None):
        if row != self.row:
            if self.row is not None:
                self.row.remove_css_class('drop-row')
            self.row = row
            if self.row is not None:
                self.row.add_css_class('drop-row')

    @staticmethod
    def action_cb(self, x, y):
        row, x, y = misc.find_descendant_at_xy(self.get_widget(), x, y, 1)
        if row is None:
            row = self.get_widget().get_last_child()
        elif y < row.get_height() / 2:
            row = row.get_prev_sibling()
        self.set_row(row)
        return Gdk.DragAction.MOVE

    # @staticmethod
    # def leave_cb(self):
    #     # print('leave')
    #     self.set_row()

    @staticmethod
    def drop_cb(self, value, x, y, add_items):
        add_items(value.values, self.row.get_first_child().get_first_child().pos + 1 if self.row is not None else 0)
        return True
