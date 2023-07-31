# coding: utf-8
#
# Graphical Asynchronous Music Player Client
#
# Copyright (C) 2015-2022 Itaï BEN YAACOV
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
from gi.repository import GObject
from gi.repository import Gio
from gi.repository import Gtk
from gi.repository import Pango

import re
import ast
import cairo

from ..util.record import Record
from ..util.misc import get_modifier_state

from . import column


class Store(Gio.ListStore):
    def __init__(self):
        super().__init__(item_type=Record)

    def set(self, records):
        self.remove_all()
        for record in records:
            self.append(Record(record))


class StoreFilter(Gtk.FilterListModel):
    filter_active = GObject.Property(type=bool, default=False)

    # __gsignals__ = {
    #     'record-new': (GObject.SIGNAL_ACTION, None, (Gtk.TreeIter,)),
    #     'record-delete': (GObject.SIGNAL_ACTION, None, (Gtk.TreeIter,)),
    # }

    # def __init__(self):
    #     self.store = Store()
    #     super().__init__(model=self.store)

    # def remove(self, i):
    #     return self.store.remove(self.convert_iter_to_child_iter(i))

    # def insert_after(self, i):
    #     if self.filter_active:
    #         raise Exception(_("Cannot add to a filtered list"))
    #     success, j = self.convert_child_iter_to_iter(self.store.insert_after(None if i is None else self.convert_iter_to_child_iter(i)))
    #     return j


# class StoreSort(Gtk.SortListModel):
#     filter_active = GObject.Property(type=bool, default=False)

#     # __gsignals__ = {
#     #     'record-delete': (GObject.SIGNAL_ACTION, None, (Gtk.TreeIter,)),
#     # }

#     def __init__(self):
#         self.store = StoreFilter()
#         super().__init__(model=self.store)
#         self.bind_property('filter-active', self.store, 'filter-active')


class RecordView(Gtk.ColumnView):
    def __init__(self, fields, item_widget, item_bind_hooks, **kwargs):
        super().__init__(**kwargs)
        self.fields = fields
        self.item_widget = item_widget
        self.item_bind_hook = item_bind_hooks
        self.columns = self.get_columns()
        self.columns_by_name = {}
        for name in fields.order:
            name = name.string
            self.columns_by_name[name] = column.FieldColumn(name, self.fields.fields[name], item_widget, item_bind_hooks)
            self.append_column(self.columns_by_name[name])

        # self.connect('destroy', self.destroy_cb)
        self.columns.connect('items-changed', self.columns_changed_cb)
        self.fields.order.connect('items-changed', self.fields_order_changed_cb)

        # self.set_search_equal_func(lambda store, col, key, i: not any(isinstance(value, str) and key.lower() in value.lower() for value in store.get_record(i).get_data().values()))

        # if self.sortable:
        #     store = self.get_model()
        #     for i, name in enumerate(self.fields.order):
        #         self.columns_by_name[name].set_sort_column_id(i)
        #         store.set_sort_func(i, self.sort_func, name)

        # self.connect('drag-data-get', self.drag_data_get_cb)

        self.bind_hooks = []

    def rebind_columns(self):
        for col in self.columns_by_name.values():
            col.rebind_all()

    # @staticmethod
    # def destroy_cb(self):
    #     self.fields.disconnect_by_func(self.fields_notify_order_cb)
    #     self.disconnect_by_func(self.columns_changed_cb)
    #     del self.columns_by_name

    def columns_changed_cb(self, columns, position, removed, added):
        self.fields.order.handler_block_by_func(self.fields_order_changed_cb)
        self.fields.order[position:position + removed] = [column.StringObject(col.name) for col in columns[position:position + added]]
        self.fields.order.handler_unblock_by_func(self.fields_order_changed_cb)

    def fields_order_changed_cb(self, order, position, removed, added):
        self.columns.handler_block_by_func(self.columns_changed_cb)
        for col in list(self.columns[position:position + removed]):
            self.remove_column(col)
        for i in range(position, position + added):
            self.insert_column(i, self.columns_by_name[order[i].string])
        self.columns.handler_unblock_by_func(self.columns_changed_cb)


class View(Gtk.Box):
    def __init__(self, fields, sortable):
        self.bind_hooks = []
        self.sortable = sortable

        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.filter_box = Gtk.Box(visible=False)
        self.store = Store()
        self.store_filter = StoreFilter(model=self.store)
        self.store_selection = Gtk.MultiSelection(model=self.store_filter)
        self.record_view = RecordView(fields, lambda: Gtk.Label(halign=Gtk.Align.START, hexpand=True, vexpand=True), self.bind_hooks, model=self.store_selection, vexpand=True, enable_rubberband=True, receives_default=True, show_column_separators=True, show_row_separators=True)
        # print(list(self.record_view.observe_children()))
        # self.list_item_widget = self.record_view.observe_children()[0]
        # self.column_list_view = self.record_view.observe_children()[1]
        # help(self.list_item_widget)

        self.scrolled_view = Gtk.ScrolledWindow(child=self.record_view, focusable=False)
        self.append(self.filter_box)
        self.append(self.scrolled_view)

        # self.connect('destroy', self.destroy_cb)

        # self.set_search_equal_func(lambda store, col, key, i: not any(isinstance(value, str) and key.lower() in value.lower() for value in store.get_record(i).get_data().values()))

        # if self.sortable:
        #     store = self.get_model()
        #     for i, name in enumerate(self.fields.order):
        #         self.columns_by_name[name].set_sort_column_id(i)
        #         store.set_sort_func(i, self.sort_func, name)

        # self.connect('drag-data-get', self.drag_data_get_cb)

    # @staticmethod
    # def destroy_cb(self):
    #     self.fields.disconnect_by_func(self.fields_notify_order_cb)
    #     self.disconnect_by_func(self.columns_changed_cb)
    #     del self.columns_by_name

    def columns_changed_cb(self, columns, position, removed, added):
        self.fields.order.handler_block_by_func(self.fields_order_changed_cb)
        self.fields.order[position:position + removed] = [column.StringObject(col.name) for col in columns[position:position + added]]
        self.fields.order.handler_unblock_by_func(self.fields_order_changed_cb)

    def fields_order_changed_cb(self, order, position, removed, added):
        self.columns.handler_block_by_func(self.columns_changed_cb)
        for col in list(self.columns[position:position + removed]):
            self.record_view.remove_column(col)
        for i in range(position, position + added):
            self.record_view.insert_column(i, self.columns_by_name[order[i].string])
        self.columns.handler_unblock_by_func(self.columns_changed_cb)

    # @staticmethod
    # def sort_func(store, i, j, name):
    #     try:
    #         v1 = getattr(store.get_record(i), name)
    #         v2 = getattr(store.get_record(j), name)
    #         return 0 if v1 == v2 else -1 if v1 is None or (v2 is not None and v1 < v2) else 1
    #     except AttributeError:
    #         return 0

    # def get_selection_rows(self):
    #     store, paths = self.get_selection().get_selected_rows()
    #     return [store.get_record(store.get_iter(p)).get_data_clean() for p in paths], [Gtk.TreeRowReference.new(store, p) for p in paths]

    # def clipboard_paste_cb(self, clipboard, raw, before):
    #     path, column = self.get_cursor()
    #     try:
    #         records = ast.literal_eval(raw)
    #     except Exception:
    #         return
    #     if not (isinstance(records, list) and all(isinstance(record, dict) for record in records)):
    #         return
    #     self.paste_at(records, path, before)

    # def paste_at(self, records, path, before):
    #     selection = self.get_selection()
    #     selection.unselect_all()
    #     store = self.get_model()
    #     i = store.get_iter(path) if path else None
    #     if before:
    #         i = store.iter_previous(i) if i else store.iter_nth_child(None, max(store.iter_n_children(None) - 1, 0))
    #     cursor_set = False
    #     for record in records:
    #         j = store.insert_after(i)
    #         store.set_row(j, record)
    #         ref = Gtk.TreeRowReference.new(store, store.get_path(j))
    #         store.emit('record-new', j)
    #         i = store.get_iter(ref.get_path())
    #         if not cursor_set:
    #             cursor_set = True
    #             self.set_cursor(store.get_path(i))
    #         selection.select_iter(i)

    # def do_drag_begin(self, context):
    #     drag_records, context.drag_refs = self.get_selection_rows()
    #     context.data = repr(drag_records).encode()
    #     if not drag_records:
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

    # @staticmethod
    # def drag_data_get_cb(self, context, data, info, time):
    #     data.set(data.get_target(), 8, context.data)

    # def do_drag_data_delete(self, context):
    #     self.get_model().delete_refs(context.drag_refs)
    #     context.drag_refs = []

    # def do_drag_data_received(self, context, x, y, data, info, time):
    #     path, pos = self.get_dest_row_at_pos(x, y)
    #     records = ast.literal_eval(data.get_data().decode())
    #     self.paste_at(records, path, pos in [Gtk.TreeViewDropPosition.BEFORE, Gtk.TreeViewDropPosition.INTO_OR_BEFORE])

    # def do_drag_end(self, context):
    #     del context.drag_refs

    # def do_drag_motion(self, context, x, y, time):
    #     dest = self.get_dest_row_at_pos(x, y)
    #     if dest is None:
    #         return False
    #     self.set_drag_dest_row(*dest)
    #     if context.get_actions() & Gdk.DragAction.MOVE and not get_modifier_state() & Gdk.ModifierType.CONTROL_MASK:
    #         action = Gdk.DragAction.MOVE
    #     else:
    #         action = Gdk.DragAction.COPY
    #     Gdk.drag_status(context, action, time)
    #     return True


# class RecordTreeViewFilter(RecordTreeViewBase):
#     __gsignals__ = {
#         'changed': (GObject.SIGNAL_RUN_LAST, None, ()),
#     }

#     def __init__(self, unit_misc, filter_, fields, **kwargs):
#         super().__init__(Store, fields, self.data_func, can_focus=True, headers_visible=False, **kwargs)
#         self.unit_misc = unit_misc
#         store = self.get_model()
#         self.filter_ = filter_
#         store.set_value(store.append(), 0, filter_)
#         self.get_selection().set_mode(Gtk.SelectionMode.NONE)
#         for name, col in self.columns_by_name.items():
#             col.renderer.set_property('editable', True)
#             col.renderer.connect('editing-started', self.renderer_editing_started_cb, name)
#         # self.connect('button-press-event', self.button_press_event_cb)

#     @staticmethod
#     def button_press_event_cb(self, event):
#         pos = self.get_path_at_pos(event.x, event.y)
#         if not pos:
#             return False
#         path, col, cx, xy = pos
#         self.set_cursor_on_cell(path, col, col.renderer, True)
#         return True

#     def renderer_editing_started_cb(self, renderer, editable, path, name):
#         editable.connect('editing-done', self.editing_done_cb, name)
#         self.unit_misc.block_fragile_accels = True
#         self.handler_block_by_func(self.button_press_event_cb)

#     def editing_done_cb(self, editable, name):
#         self.handler_unblock_by_func(self.button_press_event_cb)
#         self.unit_misc.block_fragile_accels = False
#         if editable.get_property('editing-canceled'):
#             return
#         value = editable.get_text() or None
#         if value != getattr(self.filter_, name):
#             if value:
#                 setattr(self.filter_, name, value)
#             else:
#                 delattr(self.filter_, name)
#             self.emit('changed')

#     green = Gdk.RGBA()
#     green.parse('pale green')
#     yellow = Gdk.RGBA()
#     yellow.parse('yellow')

#     @staticmethod
#     def data_func(column, renderer, store, i, arg):
#         renderer.set_property('background-rgba', RecordTreeViewFilter.green if renderer.get_property('text') is None else RecordTreeViewFilter.yellow)


# class ColumnViewWithFilter(Gtk.Box):
#     active = GObject.Property(type=bool, default=False)

#     def __init__(self, unit_misc, treeview):
#         super().__init__(orientation=Gtk.Orientation.VERTICAL)

#         self.filter_ = Record()
#         self.filter_treeview = RecordTreeViewFilter(unit_misc, self.filter_, treeview.fields)

#         filter_scroller = Gtk.ScrolledWindow(can_focus=False)
#         filter_scroller.set_child(self.filter_treeview)
#         filter_scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
#         self.append(filter_scroller)

#         self.scroller = Gtk.ScrolledWindow(can_focus=False)
#         self.scroller.set_child(treeview)
#         self.append(self.scroller)
#         self.treeview = treeview
#         treeview.bind_property('hadjustment', self.filter_treeview, 'hadjustment', GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.BIDIRECTIONAL)
#         self.bind_property('active', self.filter_treeview, 'visible')
#         self.bind_property('active', treeview.get_model(), 'filter-active')
#         self.connect('notify::active', self.notify_active_cb)
#         self.filter_treeview.connect('changed', lambda _: self.treeview.get_model().refilter())
#         self.treeview.get_model().set_visible_func(self.visible_func)
#         self.active = False

#     @staticmethod
#     def notify_active_cb(self, param):
#         self.treeview.get_model().refilter()

#     def visible_func(self, store, i, _):
#         if not self.active:
#             return True
#         record = store.get_record(i)
#         if record is None:
#             return False
#         for key, value in self.filter_.get_data().items():
#             if re.search(value, getattr(record, key) or '', re.IGNORECASE) is None:
#                 return False
#         return True
