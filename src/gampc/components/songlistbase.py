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
from gi.repository import GObject
from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import Gtk

import ampd

from ..util import record
from ..util import misc
from ..util import resource
from ..util import dialog
from ..ui import view
from ..ui import treelist
from . import component



TRY_DND = False


class SongListBase(component.Component):
    sortable = True

    duplicate_test_columns = []

    def __init__(self, unit, *args, **kwargs):
        super().__init__(unit, *args, **kwargs)

        self.widget = self.view = view.View(self.fields, self.__class__.sortable, unit.unit_misc)
        self.view.record_view.add_css_class('songlistbase')
        self.focus_widget = self.view.record_view

        self.songlistbase_actions = self.add_actions_provider('songlistbase')
        self.songlistbase_actions.add_action(resource.Action('reset', self.action_reset_cb))
        self.songlistbase_actions.add_action(resource.Action('copy', self.action_copy_delete_cb))

        if TRY_DND:
            self.setup_drag()

        self.songlistbase_actions.add_action(Gio.PropertyAction(name='filter', object=self.view, property_name='filtering'))

        self.setup_context_menu(f'{self.name}.context', self.view)
        self.signal_handler_connect(self.view.record_view, 'activate', self.view_activate_cb)
        if self.duplicate_test_columns:
            self.signal_handler_connect(self.view.record_store, 'items-changed', self.find_duplicates)

        self.view.bind_hooks.append(self.duplicate_bind_hook)

    def shutdown(self):
        del self.songlistbase_actions
        self.view.cleanup()
        super().shutdown()

    def get_current_position(self):
        if (row := self.view.record_view_rows.get_focus_child()) is not None:
            return row.get_first_child()._pos
        found, i, pos = Gtk.BitsetIter.init_first(self.view.record_selection.get_selection())
        if found and not i.next()[0]:
            return pos
        else:
            return None

    @ampd.task
    async def view_activate_cb(self, view, position):
        if self.unit.unit_persistent.protect_active:
            return
        filename = self.view.record_selection[position].file
        records = await self.ampd.playlistfind('file', filename)
        if records:
            record_id = sorted(records, key=lambda record: record['Pos'])[0]['Id']
        else:
            record_id = await self.ampd.addid(filename)
        await self.ampd.playid(record_id)

    def duplicate_bind_hook(self, label, item, name):
        label.get_parent().set_css_classes([])
        duplicate = item._duplicate
        if duplicate is not None:
            label.get_parent().add_css_class(f'duplicate{duplicate % 64}')

    def set_songs(self, songs, *, set_fields=True):
        songs = list(songs)
        if set_fields:
            self.set_extra_fields(songs)
        self._set_songs(songs)

    def _set_songs(self, songs):
        self.view.record_store[:] = map(record.Record, songs)

    def set_extra_fields(self, songs):
        for song in songs:
            self.fields.set_derived_fields(song)

    def find_duplicates(self, *args):
        model = self.view.record_store
        marker = 0
        firsts = {}
        for i, record_ in enumerate(model):
            if record_.file == self.unit.unit_server.SEPARATOR_FILE:
                continue
            test = tuple(record_[field] for field in self.duplicate_test_columns)
            first = firsts.get(test)
            if first is None:
                firsts[test] = i
                if record_._duplicate is not None:
                    del record_._duplicate
            else:
                if model[first]._duplicate is None:
                    model[first]._duplicate = marker
                    marker += 1
                record_._duplicate = model[first]._duplicate
        self.view.record_view.rebind_columns()

    def action_reset_cb(self, action, parameter):
        self.view.filter_record.set_data({})
        self.view.filtering = False
        if self.sortable:
            self.view.record_view.sort_by_column(None, Gtk.SortType.ASCENDING)

    def action_copy_delete_cb(self, action, parameter):
        records = self.view.get_selection_records()
        if action.get_name() in ['copy', 'cut']:
            self.widget.get_clipboard().set_content(self.content_from_records(records))
        if action.get_name() in ['delete', 'cut']:
            self.remove_records(records)

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
        self.drag_source.set_icon(Gtk.IconTheme.get_for_display(misc.get_display()).lookup_icon('face-cool', None, 48, 1, Gtk.TextDirection.NONE, 0), 5, 5)
        self.signal_handler_connect(self.drag_source, 'prepare', self.drag_prepare_cb)
        self.signal_handler_connect(self.drag_source, 'drag-begin', self.drag_begin_cb)
        self.signal_handler_connect(self.drag_source, 'drag-cancel', self.drag_cancel_cb)
        self.signal_handler_connect(self.drag_source, 'drag-end', self.drag_end_cb)
        self.view.record_view_rows.add_controller(self.drag_source)

        self.drag_key_controller = Gtk.EventControllerKey()
        self.signal_handler_connect(self.drag_key_controller, 'key-pressed', self.drag_key_pressed_cb, self.drag_source)
        self.view.record_view_rows.add_controller(self.drag_key_controller)

    def drag_prepare_cb(self, source, x, y):
        source.records = self.view.get_selection_records()
        if not source.records:
            row, x, y = misc.find_descendant_at_xy(self.view.record_view_rows, x, y, 1)
            if row is not None:
                source.records = [self.view.record_selection[row.get_first_child()._pos]]
            else:
                return None
        source.set_content(self.content_from_records(source.records))
        return self.content_from_records(source.records)

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
            self.remove_records(source.records)
        del source.records

    @staticmethod
    def drag_key_pressed_cb(controller, keyval, keycode, modifiers, source):
        if keyval == Gdk.KEY_Escape:
            source.drag_cancel()
        return False


class SongListBaseEditableMixin(SongListBase):
    editable = GObject.Property(type=bool, default=True)

    sortable = False

    def __init__(self, unit, *args, **kwargs):
        super().__init__(unit, *args, **kwargs)
        self.songlistbase_actions.add_action(resource.Action('paste', self.action_paste_cb))
        self.songlistbase_actions.add_action(resource.Action('paste-before', self.action_paste_cb))
        self.songlistbase_actions.add_action(resource.Action('delete', self.action_copy_delete_cb))
        self.songlistbase_actions.add_action(resource.Action('cut', self.action_copy_delete_cb))
        self.signal_handler_connect(self, 'notify::editable', self.check_editable)
        self.signal_handler_connect(self.view, 'notify::filtering', self.check_editable)

        self.setup_drop()

    def check_editable(self, *args):
        editable = self.editable and not self.view.filtering
        for name in ['paste', 'paste-before', 'delete', 'cut']:
            self.songlistbase_actions.lookup(name).set_enabled(editable)
        if TRY_DND:
            self.drag_source.set_actions(Gdk.DragAction.COPY | Gdk.DragAction.MOVE if editable else Gdk.DragAction.COPY)

    def action_paste_cb(self, action, parameter):
        self.widget.get_clipboard().read_text_async(None, self.action_paste_finish_cb, action.get_name().endswith('-before'))

    def action_paste_finish_cb(self, clipboard, result, before):
        try:
            data = self.data_from_raw(clipboard.read_text_finish(result))
        except GLib.GError as error:
            print(error)
            return
        row = self.view.record_view_rows.get_focus_child()
        if data is not None and row is not None:
            self.add_records_from_data(data, self.row_get_position(row, after=not before))

    def setup_drop(self):
        self.drop_target = Gtk.DropTarget(actions=Gdk.DragAction.COPY | Gdk.DragAction.MOVE, formats=Gdk.ContentFormats.parse('gchararray'))
        self.signal_handler_connect(self.drop_target, 'enter', self.drop_action_cb)
        self.signal_handler_connect(self.drop_target, 'motion', self.drop_action_cb)
        self.signal_handler_connect(self.drop_target, 'drop', self.drop_cb)
        # self.signal_handler_connect(self.drop_target, 'notify::value', misc.AutoWeakMethod(self.drop_notify_value_cb))
        # self.drop_target.set_preload(True)
        self.view.record_view_rows.add_controller(self.drop_target)

        self.drop_key_controller = Gtk.EventControllerKey()
        self.signal_handler_connect(self.drop_key_controller, 'key-pressed', self.drop_key_pressed_cb, self.drop_target)
        self.signal_handler_connect(self.drop_key_controller, 'modifiers', self.drop_modifiers_cb, self.drop_target)
        self.view.record_view_rows.add_controller(self.drop_key_controller)

    def drop_action_cb(self, target, x, y):
        row, x, y = misc.find_descendant_at_xy(target.get_widget(), x, y, 1)
        if row is None:
            return 0
        if target.get_value() is not None and not target.get_value().is_of_type(GLib.VariantType('as')):
            return 0
        if target.get_actions() & Gdk.DragAction.MOVE and misc.get_modifier_state() & Gdk.ModifierType.SHIFT_MASK:
            return Gdk.DragAction.MOVE
        else:
            return Gdk.DragAction.COPY

    def drop_cb(self, target, value, x, y):
        data = self.data_from_raw(value)
        if data is None:
            return
        row, x, y = misc.find_descendant_at_xy(self.view.record_view_rows, x, y, 1)
        if row is not None:
            if y < row.get_allocation().height / 2:
                before = True
            else:
                before = False
            self.add_records_from_data(data, self.row_get_position(row, after=not before))

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
        if target.get_actions() & Gdk.DragAction.MOVE and misc.get_modifier_state() & Gdk.ModifierType.SHIFT_MASK:
            pass


class SimpleDelta(GObject.Object):
    def __init__(self, records, position, push):
        super().__init__()
        self.records = records
        self.position = position
        self.push = push

    def apply(self, view, push, deselect=True):
        if not self.push:
            push = not push
        selection_model = view.get_model()
        model = selection_model.get_model()
        if isinstance(model, Gtk.FilterListModel):
            if model.get_filter() is not None:
                raise RuntimeError
            else:
                model = model.get_model()
        if push:
            model[self.position:self.position] = self.records
            selection_model.select_range(self.position, len(self.records), deselect)
        else:
            if model[self.position:self.position + len(self.records)] != self.records:
                raise RuntimeError
            model[self.position:self.position + len(self.records)] = []
            # selection_model.select_item(self.position, deselect)
            pos = self.position
            if pos == len(model):
                pos -= 1
            if pos >= 0:
                view.scroll_to(pos, None, Gtk.ListScrollFlags.FOCUS | Gtk.ListScrollFlags.SELECT, None)


class MetaDelta(GObject.Object):
    def __init__(self, deltas, push):
        super().__init__()
        self.deltas = deltas
        self.push = push

    def apply(self, view, push):
        if not self.push:
            push = not push
        view.get_model().unselect_all()
        if push:
            for delta in self.deltas:
                delta.apply(view, True, False)
        else:
            for delta in reversed(self.deltas):
                delta.apply(view, False, False)


class SongListBaseEditStackMixin(SongListBaseEditableMixin, SongListBase):  # Must take in SongListBase or GObject property doesn't work
    delta_pos = GObject.Property(type=int, default=0)

    def __init__(self, unit, *args, **kwargs):
        super().__init__(unit, *args, **kwargs)
        self.songlistbase_actions.add_action(resource.Action('save', self.action_save_cb))
        # self.songlistbase_actions.add_action(resource.Action('reset', self.action_reset_cb))
        self.songlistbase_actions.add_action(resource.Action('undo', self.action_do_cb))
        self.songlistbase_actions.add_action(resource.Action('redo', self.action_do_cb))

        self.deltas = Gio.ListStore()

    def delta_push(self):
        self.deltas[self.delta_pos].apply(self.view.record_view, True)
        self.delta_pos += 1
        self.edit_stack_changed()

    def delta_pop(self):
        self.delta_pos -= 1
        self.deltas[self.delta_pos].apply(self.view.record_view, False)
        self.edit_stack_changed()

    def remove_records(self, records):
        if not records:
            return
        indices = []
        for i, record_ in enumerate(self.view.record_selection):
            if record_ in records:
                indices.append(i)
                records.remove(record_)
        if records:
            raise RuntimeError
        deltas = []
        i = j = indices[0]
        for k in indices[1:] + [0]:
            j += 1
            if j != k:
                deltas.append(SimpleDelta(self.view.record_selection[i:j], i, True))
                i = j = k
        self.deltas[self.delta_pos:] = [MetaDelta(deltas, False)]
        self.delta_push()

    def add_records(self, records, position):
        if not records:
            return
        self.deltas[self.delta_pos:] = [SimpleDelta(records, position, True)]
        self.delta_push()

    @ampd.task
    async def add_records_from_data(self, data, position):
        self.add_records(await self.records_from_data(data), position)

    def edit_stack_changed(self):
        self.songlistbase_actions.lookup_action('save').set_enabled(True)
        self.songlistbase_actions.lookup_action('undo').set_enabled(self.delta_pos > 0)
        self.songlistbase_actions.lookup_action('redo').set_enabled(self.delta_pos < len(self.deltas))

    def action_do_cb(self, action, parameter):
        if action.get_name() == 'redo':
            self.delta_push()
        elif action.get_name() == 'undo':
            self.delta_pop()
        else:
            raise RuntimeError
        self.edit_stack_changed()

    @ampd.task
    async def action_reset_cb(self, action, parameter):
        if not self.deltas:
            return
        if not await dialog.AsyncMessageDialog(transient_for=self.widget.get_root(), message=_("Reset and lose all modifications?")).run():
            return
        while self.delta_pos:
            self.delta_pop()
        self.deltas[:] = []
        self.edit_stack_changed()


class SongListBasePaneMixin(component.ComponentPaneMixin):
    def __init__(self, unit, **kwargs):
        super().__init__(unit, **kwargs)
        self.left_store = Gtk.MultiSelection(model=self.init_left_store())
        self.left_view.set_model(self.left_store)
        self.left_selected = []
        self.left_selected_item = None

        self.signal_handler_connect(self.left_view, 'activate', self.left_view_activate_cb)
        self.signal_handler_connect(self.left_store, 'selection_changed', self.left_selection_changed_cb)
        self.left_store.select_item(0, True)

        self.focus_widget = self.left_view

    def init_left_store(self):
        return self.unit.left_store

    def left_selection_changed_cb(self, selection, position, n_items):
        self.left_selected = []
        found, i, pos = Gtk.BitsetIter.init_first(selection.get_selection())
        while found:
            self.left_selected.append(pos)
            found, pos = i.next()
        if len(self.left_selected) == 1:
            self.left_selected_item = selection[self.left_selected[0]].get_item()
        else:
            self.left_selected_item = None

    @staticmethod
    def left_view_activate_cb(view, position):
        row = view.get_model()[position]
        if row.is_expandable():
            row.set_expanded(not row.get_expanded())


class UnitMixinSongListBase(component.UnitMixinComponent):
    def __init__(self, name, manager, *, menus=[]):
        self.REQUIRED_UNITS = ['misc', 'songlistbase'] + self.REQUIRED_UNITS
        super().__init__(name, manager, menus=menus + ['context'])
