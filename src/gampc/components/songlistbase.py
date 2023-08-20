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

import ampd

from ..util import misc
from ..util import resource
from ..ui import view
from ..ui import treelist
from . import component


class SongListBase(component.Component):
    editable = False
    duplicate_test_columns = []
    duplicate_field = '_duplicate'

    RECORD_NEW = 1
    RECORD_DELETED = 2
    RECORD_MODIFIED = 3
    RECORD_UNDEFINED = 4

    STATUS_PROPERTIES = ('background-rgba', 'font', 'strikethrough')
    STATUS_PROPERTY_TABLE = {
        RECORD_NEW: (Gdk.RGBA(0.0, 1.0, 0.0, 1.0), 'bold', None),
        RECORD_DELETED: (Gdk.RGBA(1.0, 0.0, 0.0, 1.0), 'italic', True),
        RECORD_MODIFIED: (Gdk.RGBA(1.0, 1.0, 0.0, 1.0), None, None),
        RECORD_UNDEFINED: (None, 'bold italic', None),
    }

    def __init__(self, unit, *args, **kwargs):
        super().__init__(unit, *args, **kwargs)

        self.widget = self.view = view.View(self.fields, not self.editable, unit.unit_misc)
        self.view.record_view.add_css_class('songlistbase')
        self.focus_widget = self.view.record_view

        self.songlistbase_actions = self.add_actions_provider('songlistbase')
        self.songlistbase_actions.add_action(resource.Action('reset', self.action_reset_cb))
        self.songlistbase_actions.add_action(resource.Action('copy', self.action_copy_delete_cb))

        # self.setup_drag(self.editable)

        if self.editable:
            self.songlistbase_actions.add_action(resource.Action('paste', self.action_paste_cb))
            self.songlistbase_actions.add_action(resource.Action('paste-before', self.action_paste_cb))
            self.songlistbase_actions.add_action(resource.Action('delete', self.action_copy_delete_cb))
            self.songlistbase_actions.add_action(resource.Action('cut', self.action_copy_delete_cb))
            # self.setup_drop()

        self.songlistbase_actions.add_action(Gio.PropertyAction(name='filter', object=self.view, property_name='filtering'))

        self.setup_context_menu(f'{self.name}.context', self.view)
        self.view.record_view.connect('activate', self.view_activate_cb)

        self.view.bind_hooks.append(self.duplicate_bind_hook)

    def shutdown(self):
        # self.cleanup_drag()
        # if self.editable:
        #     self.cleanup_drop()
        del self.songlistbase_actions
        self.view.record_view.disconnect_by_func(self.view_activate_cb)
        self.view.cleanup()
        super().shutdown()

    # def set_editable(self, editable):
    #     for name in ['paste', 'paste-before', 'delete', 'cut']:
    #         action_ = self.songlistbase_actions.lookup(name)
    #         if action_ is not None:
    #             action_.set_enabled(editable)

    @ampd.task
    async def view_activate_cb(self, view, position):
        if self.unit.unit_persistent.protect_active:
            return
        filename = self.view.store_selection[position].file
        records = await self.ampd.playlistfind('file', filename)
        if records:
            record_id = sorted(records, key=lambda record: record['Pos'])[0]['Id']
        else:
            record_id = await self.ampd.addid(filename)
        await self.ampd.playid(record_id)

    def duplicate_bind_hook(self, label, item, name):
        label.get_parent().set_css_classes([])
        duplicate = item[self.duplicate_field]
        if duplicate is not None:
            label.get_parent().add_css_class(f'duplicate{duplicate % 64}')

        # status = store.get_record(i)._status
        # if status is not None:
        #     for k, p in enumerate(self.STATUS_PROPERTIES):
        #         if self.STATUS_PROPERTY_TABLE[status][k] is not None:
        #             renderer.set_property(p, self.STATUS_PROPERTY_TABLE[status][k])

    def set_records(self, records, set_fields=True):
        records = list(records)
        if set_fields:
            self.records_set_fields(records)
        if self.duplicate_test_columns:
            self.find_duplicates(records, self.duplicate_test_columns)
        self.view.store.set_records(records)
        self.view.record_view.rebind_columns()

    def records_set_fields(self, records):
        self.fields.records_set_fields(records)

    def find_duplicates(self, records, test_fields):
        dup_marker = 0
        dup_dict = {}
        for record in records:
            if record['file'] == self.unit.unit_server.SEPARATOR_FILE:
                continue
            test = tuple(record.get(field) for field in test_fields)
            duplicates = dup_dict.get(test)
            if duplicates:
                if len(duplicates) == 1:
                    duplicates[0][self.duplicate_field] = dup_marker
                    dup_marker += 1
                record[self.duplicate_field] = duplicates[0][self.duplicate_field]
                duplicates.append(record)
            else:
                dup_dict[test] = [record]
                record.pop(self.duplicate_field, None)

    def action_reset_cb(self, action, parameter):
        self.view_filter.filter_.set_data({})
        self.view_filter.active = False
        if self.sortable: ### !!!!!
            self.widget.store.set_sort_column_id(-1, Gtk.SortType.ASCENDING)

    records_added_cb = records_removed_cb = NotImplemented

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

    def action_copy_delete_cb(self, action, parameter):
        records = self.view.get_selection_records()
        if action.get_name() in ['copy', 'cut']:
            misc.get_clipboard().set_content(misc.content_filenames_from_records(records))
        if action.get_name() in ['delete', 'cut']:
            self.remove_records(records)

    def paste_at_row(self, filenames, row, before):
        position = row.get_first_child()._pos
        if not before:
            position += 1
        self.add_filenames(position, filenames)

    def action_paste_cb(self, action, parameter):
        misc.get_clipboard().read_text_async(None, self.action_paste_finish_cb, action.get_name().endswith('-before'))

    def action_paste_finish_cb(self, clipboard, result, before):
        try:
            filenames = misc.filenames_from_raw(clipboard.read_text_finish(result))
        except GLib.GError as error:
            print(error)
            return
        row = self.view.record_view_rows.get_focus_child()
        if filenames is not None and row is not None:
            self.paste_at_row(filenames, row, before)

    # def setup_drag(self, editable):
    #     self.drag_source = Gtk.DragSource(actions=Gdk.DragAction.COPY | Gdk.DragAction.MOVE if editable else Gdk.DragAction.COPY)
    #     self.drag_source.set_icon(Gtk.IconTheme.get_for_display(misc.get_display()).lookup_icon('face-cool', None, 48, 1, Gtk.TextDirection.NONE, 0), 5, 5)
    #     self.drag_source.connect('prepare', self.drag_prepare_cb)
    #     self.drag_source.connect('drag-begin', self.drag_begin_cb)
    #     self.drag_source.connect('drag-cancel', self.drag_cancel_cb)
    #     self.drag_source.connect('drag-end', self.drag_end_cb)
    #     self.view.record_view_rows.add_controller(self.drag_source)

    #     self.drag_key_controller = Gtk.EventControllerKey()
    #     self.drag_key_controller.connect('key-pressed', self.drag_key_pressed_cb, self.drag_source)
    #     self.view.record_view_rows.add_controller(self.drag_key_controller)

    # def cleanup_drag(self):
    #     self.view.record_view_rows.remove_controller(self.drag_source)
    #     self.view.record_view_rows.remove_controller(self.drag_key_controller)
    #     del self.drag_source
    #     del self.drag_key_controller

    # def drag_prepare_cb(self, source, x, y):
    #     source.records = self.view.get_selection_records()
    #     if not source.records:
    #         row, x, y = misc.find_descendant_at_xy(self.view.record_view_rows, x, y, 1)
    #         if row is not None:
    #             source.records = [self.view.store_selection[row.get_first_child()._pos]]
    #         else:
    #             return None
    #     source.set_content(self.content_from_records(source.records))
    #     return self.content_from_records(source.records)

    # def drag_begin_cb(self, source, drag):
    #     pass

    # def drag_cancel_cb(self, source, drag, reason):
    #     print(2, source.get_content(), drag, reason)
    #     source.set_content(None)
    #     drag.drop_done(False)
    #     return False

    # def drag_end_cb(self, source, drag, delete):
    #     if delete:
    #         self.remove_records(source.records)
    #     del source.records

    # @staticmethod
    # def drag_key_pressed_cb(controller, keyval, keycode, modifiers, source):
    #     if keyval == Gdk.KEY_Escape:
    #         source.drag_cancel()
    #     return False

    # def setup_drop(self):
    #     self.drop_target = Gtk.DropTarget.new(GLib.Variant, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
    #     self.drop_target.connect('enter', self.drop_action_cb)
    #     self.drop_target.connect('motion', self.drop_action_cb)
    #     self.drop_target.connect('drop', self.drop_cb)
    #     # self.drop_target.connect('notify::value', misc.AutoWeakMethod(self.drop_notify_value_cb))
    #     # self.drop_target.set_preload(True)
    #     self.view.record_view_rows.add_controller(self.drop_target)

    #     self.drop_key_controller = Gtk.EventControllerKey()
    #     self.drop_key_controller.connect('key-pressed', self.drop_key_pressed_cb, self.drop_target)
    #     self.drop_key_controller.connect('modifiers', self.drop_modifiers_cb, self.drop_target)
    #     self.view.record_view_rows.add_controller(self.drop_key_controller)

    # def cleanup_drop(self):
    #     self.view.record_view_rows.remove_controller(self.drop_target)
    #     self.view.record_view_rows.remove_controller(self.drop_key_controller)
    #     del self.drop_target
    #     del self.drop_key_controller

    # def drop_action_cb(self, target, x, y):
    #     row, x, y = misc.find_descendant_at_xy(target.get_widget(), x, y, 1)
    #     if row is None:
    #         return 0
    #     if target.get_value() is not None and not target.get_value().is_of_type(GLib.VariantType('as')):
    #         return 0
    #     if target.get_actions() & Gdk.DragAction.MOVE and misc.get_modifier_state() & Gdk.ModifierType.SHIFT_MASK:
    #         return Gdk.DragAction.MOVE
    #     else:
    #         return Gdk.DragAction.COPY

    # def drop_cb(self, target, value, x, y):
    #     row, x, y = misc.find_descendant_at_xy(self.view.record_view_rows, x, y, 1)
    #     if row is not None:
    #         if y < row.get_allocation().height / 2:
    #             before = True
    #         else:
    #             before = False
    #         self.paste_at_row(value, row, before)

    # # def drop_notify_value_cb(self, target, param):
    # #     drop = target.get_current_drop()
    # #     if drop is None:
    # #         return
    # #     if not target.get_value().is_of_type(GLib.VariantType('as')):
    # #         target.reject()

    # @staticmethod
    # def drop_key_pressed_cb(controller, keyval, keycode, modifiers, target):
    #     if keyval == Gdk.KEY_Escape:
    #         target.get_drop().finish(0)
    #         target.reject()
    #     return False

    # @staticmethod
    # def drop_modifiers_cb(controller, modifiers, target):
    #     if target.get_actions() & Gdk.DragAction.MOVE and misc.get_modifier_state() & Gdk.ModifierType.SHIFT_MASK:
    #         pass


class SongListBaseWithEditDel(SongListBase):
    def __init__(self, unit, *args, **kwargs):
        super().__init__(unit, *args, **kwargs)
        self.songlistbase_actions.add_action(resource.Action('save', self.action_save_cb))
        self.songlistbase_actions.add_action(resource.Action('undelete', self.action_undelete_cb))

    def action_undelete_cb(self, action, parameter):
        store, paths = self.view.get_selection().get_selected_rows()
        for p in paths:
            i = self.widget.store.get_iter(p)
            if self.widget.store.get_record(i)._status == self.RECORD_DELETED:
                del self.widget.store.get_record(i)._status
        self.view.queue_draw()

    def record_delete_cb(self, store, i):
        if self.widget.store.get_record(i)._status == self.RECORD_UNDEFINED:
            return
        self.set_modified()
        if self.widget.store.get_record(i)._status == self.RECORD_NEW:
            self.widget.store.remove(i)
        else:
            self.widget.store.get_record(i)._status = self.RECORD_DELETED
            self.merge_new_del(i)
        self.view.queue_draw()

    def modify_record(self, i, record):
        _record = self.widget.store.get_record(i)
        status = _record._status
        if status == self.RECORD_UNDEFINED:
            return
        _record.set_data(record)
        self.set_modified()
        if status is None:
            _record._status = self.RECORD_MODIFIED
        self.view.queue_draw()

    def merge_new_del(self, i):
        _status = self.widget.store.get_record(i)._status
        for f in [self.widget.store.iter_previous, self.widget.store.iter_next]:
            j = f(i)
            if j and self.widget.store.get_record(j).file == self.widget.store.get_record(i).file and {_status, self.widget.store.get_record(j)._status} == {self.RECORD_DELETED, self.RECORD_NEW}:
                del self.widget.store.get_record(i)._status
                self.widget.store.remove(j)
                return


class SongListBaseWithAdd(SongListBase):
    def add_record(self, record):
        # dest = self.view.get_path_at_pos(int(self.view.context_menu_x), int(self.view.context_menu_y))
        # path = None if dest is None else dest[0]
        path, column = self.view.get_cursor()
        self.view.paste_at([record], path, False)


class SongListBaseWithEditDelNew(SongListBaseWithEditDel, SongListBaseWithAdd):
    def record_new_cb(self, store, i):
        self.set_modified()
        store.get_record(i)._status = self.RECORD_NEW
        self.merge_new_del(i)


class SongListBaseWithPane(component.ComponentMixinPaned, SongListBase):
    def __init__(self, unit):
        super().__init__(unit)
        self.left_store = Gtk.MultiSelection(model=self.init_left_store())
        self.left_view.set_model(self.left_store)

        self.left_view.connect('activate', self.left_view_activate_cb)
        self.left_store.connect('selection_changed', self.left_selection_changed_cb)
        self.left_store.select_item(0, True)

        self.focus_widget = self.left_view

    def shutdown(self):
        super().shutdown()
        self.left_store.disconnect_by_func(self.left_selection_changed_cb)

    def get_left_factory(self):
        return treelist.TreeItemFactory()

    def init_left_store(self):
        return self.unit.left_store

    def left_selection_changed_cb(self, selection, position, n_items):
        songs = []
        for i, row in enumerate(selection):
            if selection.is_selected(i):
                songs += row.get_item().songs
        self.set_records(songs)

    @staticmethod
    def left_view_activate_cb(view, position):
        row = view.get_model()[position]
        if row.is_expandable():
            row.set_expanded(not row.get_expanded())


class UnitMixinSongListBase(component.UnitMixinComponent):
    def __init__(self, name, manager, *, menus=[]):
        self.REQUIRED_UNITS = ['misc', 'songlistbase'] + self.REQUIRED_UNITS
        super().__init__(name, manager, menus=menus + ['context'])
