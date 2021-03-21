# coding: utf-8
#
# Graphical Asynchronous Music Player Client
#
# Copyright (C) 2015 Itaï BEN YAACOV
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


from gi.repository import GObject, GLib, Gdk, Gtk, Pango
import re
import ast
import cairo


def format_time(time):
    time = int(time)
    hours = time // 3600
    minutes = (time // 60) % 60
    seconds = time % 60
    return '{:d}:{:02d}:{:02d}'.format(hours, minutes, seconds) if hours else '{:d}:{:02d}'.format(minutes, seconds)


def store_set_rows(store, rows, func):
    if not rows:
        store.clear()
        return
    i = store.get_iter_first()
    appending = (i is None)
    for row in rows:
        if appending:
            i = store.append()
        func(i, row)
        if not appending:
            i = store.iter_next(i)
            if i is None:
                appending = True
    if not appending:
        while store.remove(i):
            pass


def config_notify_cb(obj, param, config):
    config[param.name] = obj.get_property(param.name)


class Field(GObject.Object):
    title = GObject.Property(type=str)
    width = GObject.Property(type=int)
    visible = GObject.Property(type=bool, default=True)
    xalign = GObject.Property(type=float, default=0.0)

    get_value = None

    def __init__(self, name, title=None, min_width=50, get_value=None, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.title = title
        self.width = self.min_width = min_width
        if get_value:
            self.get_value = get_value

    def get_renderer(self):
        return Gtk.CellRendererText(ellipsize=Pango.EllipsizeMode.END, xalign=self.xalign)

    def __repr__(self):
        return "Field '{title}'".format(title=self.title)


class FieldWithTable(Field):
    def __init__(self, name, title=None, table=None, min_width=50, **kwargs):
        super().__init__(name, title, min_width, **kwargs)
        self.table = table

    def get_value(self, record):
        for field, pattern, value in self.table:
            if not field:
                return value
            else:
                match = re.search(pattern, record.get(field, ''))
                if match:
                    return match.expand(value)


class FieldFamily(GObject.Object):
    order = GObject.Property()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.old_order = self.config.access_base('order', [])
        self.order = self.config.order = []
        self.connect('notify', config_notify_cb, self.config)

        self.names = []
        self.basic_names = []
        self.derived_names = []
        self.fields = {}

    def close(self):
        self.disconnect_by_func(config_notify_cb)

    def register_field(self, field):
        if field.name in self.names:
            raise RuntimeError("Field '{name}' already registered".format(name=field.name))
        self.names.append(field.name)
        if field.get_value:
            self.derived_names.append(field.name)
        else:
            self.basic_names.append(field.name)
        self.fields[field.name] = field

        field_config = self.config.info[field.name]
        field.connect('notify', config_notify_cb, field_config)
        field.width = field_config.access('width', field.width)
        field.visible = field_config.access('visible', field.visible)
        if field.name in self.order:
            return
        if field.name not in self.old_order:
            self.order.append(field.name)
            return
        pos = self.old_order.index(field.name)
        for i, name in enumerate(self.order):
            if name not in self.old_order or self.old_order.index(name) > pos:
                self.order.insert(i, field.name)
                return
        else:
            self.order.append(field.name)

    def unregister_field(self, field):
        self.names.remove(field.name)
        if field.name in self.basic_names:
            self.basic_names.remove(field.name)
        else:
            self.derived_names.remove(field.name)
        del self.fields[field.name]
        field.disconnect_by_func(config_notify_cb)

    def record_set_fields(self, record):
        for name in self.derived_names:
            value = self.fields[name].get_value(record)
            if value is not None:
                record[name] = value

    def records_set_fields(self, records):
        for record in records:
            self.record_set_fields(record)


class FieldColumn(Gtk.TreeViewColumn):
    width_rw = GObject.Property(type=int)

    def __init__(self, field, next_data_func):
        super().__init__()
        self.field = field
        self.renderer = field.get_renderer()
        self.next_data_func = next_data_func
        field.bind_property('title', self, 'title', GObject.BindingFlags.SYNC_CREATE)
        field.bind_property('visible', self, 'visible', GObject.BindingFlags.SYNC_CREATE)
        self.set_min_width(field.min_width)
        self.connect('notify::width-rw', self.notify_width_rw_cb)
        field.bind_property('width', self, 'width-rw', GObject.BindingFlags.SYNC_CREATE)
        self.bind_property('width', field, 'width')
        self.set_resizable(True)
        self.set_reorderable(True)
        self.pack_start(self.renderer, True)
        self.set_cell_data_func(self.renderer, self.data_func)

    @staticmethod
    def notify_width_rw_cb(self, detail):
        if self.width_rw != self.get_width():
            self.set_fixed_width(self.width_rw)

    @staticmethod
    def data_func(self, renderer, store, i, arg):
        value = getattr(store.get_record(i) or Record(), self.field.name)
        renderer.set_property('text', str(value) if value is not None else None)
        self.next_data_func and self.next_data_func(self, renderer, store, i, arg)


class Record(GObject.Object):
    def __init__(self, data=None):
        super().__init__()
        self.set_data(data or {})

    def set_data(self, data):
        GObject.Object.__setattr__(self, '_data', data)

    def get_data(self):
        return self._data

    def get_data_clean(self):
        return {key: value for key, value in self._data.items() if key[0] != '_'}

    def __getattr__(self, name):
        return self._data.get(name)

    def __setattr__(self, name, value):
        self._data[name] = value

    def __delattr__(self, name):
        self._data.pop(name, None)


class StoreBase(object):
    def __iter__(self):
        i = self.iter_children(None)
        while i:
            yield i, self.get_path(i), self.get_record(i)
            i = self.iter_next(i)

    def delete_refs(self, refs):
        for ref in refs:
            i = self.get_iter(ref.get_path())
            self.emit('record-delete', i)

    def get_record(self, i):
        return self.get_value(i, 0)

    def set_row(self, i, row):
        self.set_value(i, 0, Record(row))

    def __getattr__(self, name):
        return getattr(self.store, name)


class RecordStore(StoreBase, Gtk.ListStore):
    def __init__(self):
        super().__init__(Record)

    def set_rows(self, rows):
        store_set_rows(self, rows, self.set_row)


class RecordStoreFilter(StoreBase, Gtk.TreeModelFilter):
    filter_active = GObject.Property(type=bool, default=False)

    __gsignals__ = {
        'record-new': (GObject.SIGNAL_ACTION, None, (Gtk.TreeIter,)),
        'record-delete': (GObject.SIGNAL_ACTION, None, (Gtk.TreeIter,)),
    }

    def __init__(self):
        self.store = RecordStore()
        super().__init__(child_model=self.store)

    def remove(self, i):
        return self.store.remove(self.convert_iter_to_child_iter(i))

    def insert_after(self, i):
        if self.filter_active:
            raise Exception(_("Cannot add to a filtered list"))
        success, j = self.convert_child_iter_to_iter(self.store.insert_after(None if i is None else self.convert_iter_to_child_iter(i)))
        return j


class RecordStoreSort(StoreBase, Gtk.TreeModelSort):
    filter_active = GObject.Property(type=bool, default=False)

    __gsignals__ = {
        'record-delete': (GObject.SIGNAL_ACTION, None, (Gtk.TreeIter,)),
    }

    def __init__(self):
        self.store = RecordStoreFilter()
        super().__init__(self.store)
        self.bind_property('filter-active', self.store, 'filter-active')


class AutoScrollTreeView(Gtk.TreeView):
    def __init__(self, *args, **kwargs):
        self.key_just_pressed = None

        super().__init__(*args, **kwargs)

        self.connect('key-press-event', self.key_press_event_cb)
        self.connect('cursor-changed', self.cursor_changed_cb)
        self.connect('destroy', lambda self: self.key_just_pressed and GLib.source_remove(self.key_just_pressed))

    @staticmethod
    def key_press_event_cb(self, event):
        if event.type == Gdk.EventType.KEY_PRESS:
            if self.key_just_pressed:
                GLib.source_remove(self.key_just_pressed)
            self.key_just_pressed = GLib.timeout_add(200, self.key_press_event_timeout)

    def key_press_event_timeout(self):
        self.key_just_pressed = None
        return GLib.SOURCE_REMOVE

    @staticmethod
    def cursor_changed_cb(self):
        if not self.key_just_pressed:
            return
        path, col = self.get_cursor()
        if path:
            self.scroll_to_cell(path, None, True, 0.5, 0.5)


class RecordTreeViewBase(Gtk.TreeView):
    def __init__(self, model_class, fields, data_func=None, **kwargs):
        super().__init__(model=model_class(), search_column=0, enable_search=False, enable_grid_lines=Gtk.TreeViewGridLines.BOTH, **kwargs)

        self.fields = fields
        self.cols = {name: FieldColumn(self.fields.fields[name], data_func) for name in self.fields.order}
        for name in self.fields.order:
            self.append_column(self.cols[name])

        self.connect('destroy', self.destroy_cb)
        self.connect('columns-changed', self.columns_changed_cb)
        self.fields.connect('notify::order', self.fields_notify_order_cb)

    @staticmethod
    def destroy_cb(self):
        self.fields.disconnect_by_func(self.fields_notify_order_cb)
        self.disconnect_by_func(self.columns_changed_cb)
        del self.cols

    @staticmethod
    def columns_changed_cb(self):
        self.fields.handler_block_by_func(self.fields_notify_order_cb)
        self.fields.order = [self.get_column(i).field.name for i in range(self.get_n_columns())]
        self.fields.handler_unblock_by_func(self.fields_notify_order_cb)

    def fields_notify_order_cb(self, *args):
        self.handler_block_by_func(self.columns_changed_cb)
        last_col = None
        for name in self.fields.order:
            col = self.cols[name]
            self.move_column_after(col, last_col)
            last_col = col
        self.handler_unblock_by_func(self.columns_changed_cb)


# class RecordTreeView(RecordTreeViewBase, AutoScrollTreeView):
class RecordTreeView(RecordTreeViewBase):
    def __init__(self, fields, data_func, sortable):
        super().__init__(RecordStoreSort if sortable else RecordStoreFilter, fields, data_func, visible=True, vexpand=True, rubber_banding=True)
        self.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        self.sortable = sortable

        self.set_search_equal_func(lambda store, col, key, i: not any(isinstance(value, str) and key.lower() in value.lower() for value in store.get_record(i).get_data().values()))

        if self.sortable:
            store = self.get_model()
            for i, name in enumerate(self.fields.order):
                self.cols[name].set_sort_column_id(i)
                store.set_sort_func(i, self.sort_func, name)

        self.connect('drag-data-get', self.drag_data_get_cb)

    @staticmethod
    def sort_func(store, i, j, name):
        try:
            v1 = getattr(store.get_record(i), name)
            v2 = getattr(store.get_record(j), name)
            return 0 if v1 == v2 else -1 if v1 is None or (v2 is not None and v1 < v2) else 1
        except:
            return 0

    def get_selection_rows(self):
        store, paths = self.get_selection().get_selected_rows()
        return [store.get_record(store.get_iter(p)).get_data_clean() for p in paths], [Gtk.TreeRowReference.new(store, p) for p in paths]

    def clipboard_paste_cb(self, clipboard, raw, before):
        path, column = self.get_cursor()
        try:
            records = ast.literal_eval(raw)
        except:
            return
        if not (isinstance(records, list) and all(isinstance(record, dict) for record in records)):
            return
        self.paste_at(records, path, before)

    def paste_at(self, records, path, before):
        selection = self.get_selection()
        selection.unselect_all()
        store = self.get_model()
        i = store.get_iter(path) if path else None
        if before:
            i = store.iter_previous(i) if i else store.iter_nth_child(None, max(store.iter_n_children(None) - 1, 0))
        cursor_set = False
        for record in records:
            j = store.insert_after(i)
            store.set_row(j, record)
            ref = Gtk.TreeRowReference.new(store, store.get_path(j))
            store.emit('record-new', j)
            i = store.get_iter(ref.get_path())
            if not cursor_set:
                cursor_set = True
                self.set_cursor(store.get_path(i))
            selection.select_iter(i)

    def do_drag_begin(self, context):
        drag_records, context.drag_refs = self.get_selection_rows()
        context.data = repr(drag_records).encode()
        if not drag_records:
            return
        icons = [self.create_row_drag_icon(ref.get_path()) for ref in context.drag_refs]
        xscale, yscale = icons[0].get_device_scale()
        width, height = icons[0].get_width(), icons[0].get_height() - yscale
        target = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(width / xscale), int(height * len(context.drag_refs) / yscale) + 1)
        cr = cairo.Context(target)
        cr.set_source_rgba(0, 0, 0, 1)
        cr.paint()
        y = 2
        for icon in icons:
            cr.set_source_surface(icon, 2 / xscale, y / yscale)
            cr.paint()
            y += height
        icon.flush()
        Gtk.drag_set_icon_surface(context, target)

    @staticmethod
    def drag_data_get_cb(self, context, data, info, time):
        data.set(data.get_target(), 8, context.data)

    def do_drag_data_delete(self, context):
        self.get_model().delete_refs(context.drag_refs)
        context.drag_refs = []

    def do_drag_data_received(self, context, x, y, data, info, time):
        path, pos = self.get_dest_row_at_pos(x, y)
        records = ast.literal_eval(data.get_data().decode())
        self.paste_at(records, path, pos in [Gtk.TreeViewDropPosition.BEFORE, Gtk.TreeViewDropPosition.INTO_OR_BEFORE])

    def do_drag_end(self, context):
        del context.drag_refs

    def do_drag_motion(self, context, x, y, time):
        dest = self.get_dest_row_at_pos(x, y)
        if dest is None:
            return False
        self.set_drag_dest_row(*dest)
        if context.get_actions() & Gdk.DragAction.MOVE and not Gdk.Keymap.get_default().get_modifier_state() & Gdk.ModifierType.CONTROL_MASK:
            action = Gdk.DragAction.MOVE
        else:
            action = Gdk.DragAction.COPY
        Gdk.drag_status(context, action, time)
        return True


class RecordTreeViewFilter(RecordTreeViewBase):
    __gsignals__ = {
        'changed': (GObject.SIGNAL_RUN_LAST, None, ()),
    }

    def __init__(self, unit_misc, filter_, fields, **kwargs):
        super().__init__(RecordStore, fields, self.data_func, can_focus=True, **kwargs)
        self.unit_misc = unit_misc
        store = self.get_model()
        self.filter_ = filter_
        store.set_value(store.append(), 0, filter_)
        self.get_selection().set_mode(Gtk.SelectionMode.NONE)
        for name, col in self.cols.items():
            col.renderer.set_property('editable', True)
            col.renderer.connect('editing-started', self.renderer_editing_started_cb, name)
        self.connect('button-press-event', self.button_press_event_cb)

    @staticmethod
    def button_press_event_cb(self, event):
        pos = self.get_path_at_pos(event.x, event.y)
        if not pos:
            return False
        path, col, cx, xy = pos
        self.set_cursor_on_cell(path, col, col.renderer, True)
        return True

    def renderer_editing_started_cb(self, renderer, editable, path, name):
        editable.connect('editing-done', self.editing_done_cb, name)
        self.unit_misc.block_fragile_accels = True
        self.handler_block_by_func(self.button_press_event_cb)

    def editing_done_cb(self, editable, name):
        self.handler_unblock_by_func(self.button_press_event_cb)
        self.unit_misc.block_fragile_accels = False
        if editable.get_property('editing-canceled'):
            return
        value = editable.get_text() or None
        if value != getattr(self.filter_, name):
            if value:
                setattr(self.filter_, name, value)
            else:
                delattr(self.filter_, name)
            self.emit('changed')

    green = Gdk.RGBA()
    green.parse('pale green')
    yellow = Gdk.RGBA()
    yellow.parse('yellow')

    @staticmethod
    def data_func(column, renderer, store, i, arg):
        renderer.set_property('background-rgba', RecordTreeViewFilter.green if renderer.get_property('text') is None else RecordTreeViewFilter.yellow)


class TreeViewFilter(Gtk.Box):
    active = GObject.Property(type=bool, default=False)

    def __init__(self, unit_misc, treeview):
        super().__init__(visible=True, orientation=Gtk.Orientation.VERTICAL)

        self.filter_ = Record()
        self.filter_treeview = RecordTreeViewFilter(unit_misc, self.filter_, treeview.fields)

        filter_scroller = Gtk.ScrolledWindow(visible=True)
        filter_scroller.add(self.filter_treeview)
        filter_scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.pack_start(filter_scroller, False, False, 0)

        self.scroller = Gtk.ScrolledWindow(visible=True)
        self.scroller.add(treeview)
        self.pack_start(self.scroller, True, True, 0)
        self.treeview = treeview
        treeview.bind_property('hadjustment', self.filter_treeview, 'hadjustment', GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.BIDIRECTIONAL)
        self.bind_property('active', self.filter_treeview, 'visible')
        self.bind_property('active', treeview, 'headers-visible', GObject.BindingFlags.INVERT_BOOLEAN)
        self.bind_property('active', treeview.get_model(), 'filter-active')
        self.connect('notify::active', self.notify_active_cb)
        self.filter_treeview.connect('changed', lambda _: self.treeview.get_model().refilter())
        self.treeview.get_model().set_visible_func(self.visible_func)
        self.active = False

    @staticmethod
    def notify_active_cb(self, param):
        self.treeview.get_model().refilter()

    def visible_func(self, store, i, _):
        if not self.active:
            return True
        record = store.get_record(i)
        if record is None:
            return False
        for key, value in self.filter_.get_data().items():
            if re.search(value, getattr(record, key) or '', re.IGNORECASE) is None:
                return False
        return True
