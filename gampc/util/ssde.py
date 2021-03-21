# coding: utf-8
#
# Auto-generated Gtk3 Simple Structured Data Editor
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


from gi.repository import GObject, Gdk, Gtk

from . import dialog


class InvalidData(Exception):
    pass


class EditorRow(GObject.Object):
    def __init__(self, struct, draw_label, has_value=False):
        super().__init__()
        self.struct = struct
        self.draw_label = draw_label
        self.has_value = has_value
        self.subrows = []


class DialogEditor(Gtk.Dialog):
    valid = GObject.Property(type=bool, default=True)
    editing = GObject.Property(type=bool, default=False)

    def __init__(self, struct, parent, value=None, size=None, scrolled=False):
        super().__init__(parent=parent)
        self._struct = struct
        self.parent = parent
        self.size = size

        self.set_destroy_with_parent(True)
        self.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
        self.ok_button = self.add_button(_("_OK"), Gtk.ResponseType.OK)
        self.bind_property('valid', self.ok_button, 'sensitive', GObject.BindingFlags.SYNC_CREATE)
        self.bind_property('editing', self.ok_button, 'sensitive', GObject.BindingFlags.INVERT_BOOLEAN)

        self._value_col = Gtk.TreeViewColumn.new()

        self._renderers = {}
        for target in self._struct._get_all_targets():
            renderer = target.get_renderer()
            renderer.handlers = [renderer.connect('editing-started', self.editing_started_cb)]
            if target.edited_signal:
                renderer.handlers.append(renderer.connect(target.edited_signal, target.edited_cb, self))
            self._value_col.pack_start(renderer, False)
            self._value_col.set_cell_data_func(renderer, self._data_func, target)
            self._renderers[target] = renderer

        self._store = Gtk.TreeStore(EditorRow)
        self._treeview = Gtk.TreeView(visible=True, headers_visible=False, show_expanders=True, enable_tree_lines=True, enable_search=False, model=self._store)
        self._treeview.connect('key-press-event', self._key_press_event_cb)
        self._treeview.connect('row-activated', self.row_activated_cb)
        self._treeview.insert_column_with_data_func(0, '', Gtk.CellRendererText(), self._label_data_func)
        self._treeview.append_column(self._value_col)

        if size:
            self.set_default_size(*size)
        if scrolled:
            scrolled_window = Gtk.ScrolledWindow(visible=True, expand=True)
            scrolled_window.add(self._treeview)
            self.get_content_area().add(scrolled_window)
        else:
            self.get_content_area().add(self._treeview)
        if self._struct.label:
            self.set_title(self._struct.label)

        self._row = self._struct._form_row(value)
        self._set_row(None, self._row)
        self.value = None
        self.validate()
        self.connect('destroy', self.destroy_cb)

    def edit(self):
        if self.run() == Gtk.ResponseType.OK:
            if self.size:
                (self.size[0], self.size[1]) = self.get_size()
            return self.value
        else:
            return None

    @staticmethod
    def destroy_cb(self):
        self.destroy()
        for renderer in self._renderers.values():
            for handler in renderer.handlers:
                renderer.disconnect(handler)
        del self._value_col
        if self.parent:
            self.parent.present()

    def editing_started_cb(self, renderer, editable, path):
        editable.connect('editing-done', self.editing_done_cb, self._get_row(self._store.get_iter(path)))
        self.editing = True

    def editing_done_cb(self, editable, row):
        self.editing = False
        if not editable.get_property('editing-canceled'):
            row.struct._editing_done(editable, self, row)
            self.validate()

    def validate(self):
        try:
            self.value = self._struct.get_valid_value(self._row)
            self.valid = True
        except ValueError:
            self.value = None
            self.valid = False

    def _data_func(self, column, renderer, store, i, target):
        row = self._get_row(i)
        if row.struct is target:
            renderer.set_visible(True)
            row.struct._data_func(renderer, row)
        else:
            renderer.set_visible(False)

    def _label_data_func(self, column, renderer, store, i):
        row = self._get_row(i)
        renderer.set_property('text', row.struct.label if row.draw_label else None)

    def _key_press_event_cb(self, treeview, event):
        path, column = self._treeview.get_cursor()
        if not path:
            return False
        j = self._store.get_iter(path)

        if event.state & Gdk.ModifierType.MOD1_MASK:
            k = self._store.iter_previous(j) if event.keyval == Gdk.KEY_Up else self._store.iter_next(j) if event.keyval == Gdk.KEY_Down else None
            if k:
                self._treeview.set_cursor(self._store.get_path(k))
            return True

        i = self._store.iter_parent(j)
        parent = self._get_row(i) if i else self._row
        row = self._get_row(j)
        index = -1 if not i and row == parent else parent.subrows.index(row)
        reply = parent.struct._key_press(parent, index, event)
        if reply:
            self._set_subrows(parent)
            if reply == event:
                self._key_press_event_cb(treeview, event)
            return True
        else:
            return False

    def row_activated_cb(self, treeview, path, column):
        renderer = self._renderers.get(type(self._get_row(self._store.get_iter(path)).struct))
        if renderer:
            treeview.set_cursor_on_cell(path, self._value_col, renderer, True)
        elif treeview.row_expanded(path):
            treeview.collapse_row(path)
        else:
            treeview.expand_row(path, True)

    def _get_row(self, i):
        return self._store.get_value(i, 0)

    def _set_row(self, i, row):
        if not i and row.has_value:
            i = self._store.append(None)
            row.draw_label = False
        if i:
            self._store.set_value(i, 0, row)
            row.path = self._store.get_path(i)
        else:
            row.path = None
        self._set_subrows(row)

    def _set_subrows(self, row):
        i = row.path and self._store.get_iter(row.path)
        j = self._store.iter_children(i)
        for subrow in row.subrows:
            if j:
                self._set_row(j, subrow)
                j = self._store.iter_next(j)
            else:
                self._set_row(self._store.append(i), subrow)
        if j:
            while self._store.remove(j):
                pass
        if row.path:
            self._treeview.expand_row(row.path, True)
        self.validate()


class AsyncDialogEditor(DialogEditor, dialog.AsyncDialog):
    async def edit_async(self):
        if await self.run_async() == Gtk.ResponseType.OK:
            if self.size:
                (self.size[0], self.size[1]) = self.get_size()
            return self.value
        else:
            return None


class _Struct(object):
    def __init__(self, default=None, label=None, name=None, validator=lambda value: True):
        self.default = default
        self.label = label
        self.name = name or label
        self.validator = validator
        self._substructs = []

    def edit(*args, **kwargs):
        editor = DialogEditor(*args, **kwargs)
        value = editor.edit()
        editor.destroy()
        return value

    async def edit_async(self, parent=None, *args, **kwargs):
        editor = AsyncDialogEditor(self, parent, *args, **kwargs)
        value = await editor.edit_async()
        editor.destroy()
        return value

    def _get_all_targets(self):
        return [self] if isinstance(self, _Target) else sum((substruct._get_all_targets() for substruct in self._substructs), [])

    def _get_value(self, row):
        raise NotImplementedError

    def get_valid_value(self, row):
        value = self._get_value(row)
        if self.validator and not self.validator(value):
            raise ValueError
        return value

    @staticmethod
    def _key_press(row, index, event):
        return False


class _Target(_Struct):
    edited_signal = None

    def _form_row(self, value=None, draw_label=True, has_value=True):
        row = EditorRow(self, draw_label, has_value)
        row.value = value or self.default
        return row

    def _get_value(self, row):
        return row.value


class Text(_Target):
    @staticmethod
    def get_renderer():
        return Gtk.CellRendererText(editable=True)

    @staticmethod
    def _data_func(renderer, row):
        renderer.set_property('text', row.value)

    @staticmethod
    def _editing_done(editable, editor, row):
        row.value = editable.get_text()


class Integer(_Target):
    def __init__(self, default=None, min_value=GObject.G_MININT, max_value=GObject.G_MAXINT, *args, **kwargs):
        super().__init__(default or 0, *args, **kwargs)
        self.min_value = min_value
        self.max_value = max_value

    def get_renderer(self):
        return Gtk.CellRendererSpin(editable=True, adjustment=Gtk.Adjustment(lower=self.min_value, upper=self.max_value, step_increment=1))

    @staticmethod
    def _data_func(renderer, row):
        renderer.set_property('text', str(row.value))

    @staticmethod
    def _editing_done(editable, editor, row):
        try:
            row.value = int(editable.get_text())
        except ValueError:
            pass


class Boolean(_Target):
    edited_signal = 'toggled'

    def __init__(self, default=None, *args, **kwargs):
        super().__init__(default or False, *args, **kwargs)

    @staticmethod
    def get_renderer():
        return Gtk.CellRendererToggle(xalign=0.0)

    @staticmethod
    def _data_func(renderer, row):
        renderer.set_property('active', row.value)

    @staticmethod
    def edited_cb(renderer, ps, editor):
        row = editor._get_row(editor._store.get_iter_from_string(ps))
        row.value = not row.value
        editor.validate()


class Choice(_Target):
    def __init__(self, choices, default=None, *args, **kwargs):
        if not choices:
            raise ValueError
        if not isinstance(default, tuple):
            default = (default, None)
        elif len(default) != 2:
            raise ValueError
        super().__init__(default, *args, **kwargs)
        self.default_choice = default[0]
        self.choices = {}
        self.choice_store = Gtk.ListStore()
        self.choice_store.set_column_types([str])
        for choice in choices:
            if isinstance(choice, str):
                name = choice
                self.choices[name] = None
            elif isinstance(choice, _Struct) and choice.label:
                name = choice.label
                self.choices[name] = choice
                self._substructs.append(choice)
            else:
                raise ValueError
            self.choice_store.set_value(self.choice_store.append(), 0, name)
            self.default_choice = self.default_choice or name
        if self.default_choice not in self.choices:
            raise ValueError

    def _form_row(self, value=None, draw_label=True, has_value=True):
        row = EditorRow(self, draw_label, has_value)
        value = value or self.default
        row.name, subvalue = value if isinstance(value, tuple) else (value, None)
        if row.name not in self.choices:
            row.name, subvalue = self.default_choice, None
        row.choice = self.choices[row.name]
        if row.choice:
            row.subrows = [row.choice._form_row(subvalue)]
        return row

    def _get_value(self, row):
        return (row.name, row.choice.get_valid_value(row.subrows[0])) if row.choice else row.name

    @staticmethod
    def get_renderer():
        return Gtk.CellRendererCombo(editable=True, text_column=0, has_entry=False)

    def _data_func(self, renderer, row):
        renderer.set_property('model', self.choice_store)
        renderer.set_property('text', row.name)

    def _editing_done(self, combo_box, editor, row):
        j = combo_box.get_active_iter()
        row.name = self.choice_store.get_value(j, 0)
        row.choice = self.choices[row.name]
        if row.choice:
            row.subrows = [row.choice._form_row()]
        else:
            row.subrows = []
        editor._set_subrows(row)


class Tuple(_Struct):
    def __init__(self, substructs, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._substructs = substructs

    def _get_nth_substruct(self, n):
        return self._substructs[n]

    def _form_row(self, value=None, draw_label=True, has_value=False):
        row = EditorRow(self, draw_label, has_value)
        row.subrows = [substruct._form_row(subvalue) for substruct, subvalue in self._list_substruct_value(value)]
        return row

    def _list_substruct_value(self, value):
        return ((self._get_nth_substruct(j), (value[j] if value else None)) for j in range(len(self._substructs)))

    def _get_value(self, row):
        return [subrow.struct.get_valid_value(subrow) for subrow in row.subrows]


class Dict(Tuple):
    def _list_substruct_value(self, value):
        return ((substruct, (value.get(substruct.name) if value else None)) for substruct in self._substructs)

    def _get_value(self, row):
        return {subrow.struct.name: subrow.struct.get_valid_value(subrow) for subrow in row.subrows}


def _list_key_press(row, index, event, substruct, base=0):
    if index >= base and event.state & Gdk.ModifierType.CONTROL_MASK:
        if event.keyval == Gdk.KEY_plus:
            row.subrows.insert(index, substruct._form_row())
        elif event.keyval == Gdk.KEY_minus and len(row.subrows) > base + 1:
            row.subrows.pop(index)
        elif event.keyval == Gdk.KEY_Up or event.keyval == Gdk.KEY_Down:
            if event.keyval == Gdk.KEY_Up and index > base:
                index2 = index - 1
            elif event.keyval == Gdk.KEY_Down and index < len(row.subrows) - 1:
                index2 = index + 1
            else:
                return True
            row.subrows[index], row.subrows[index2] = row.subrows[index2], row.subrows[index]
            event.state &= ~Gdk.ModifierType.CONTROL_MASK
            event.state |= Gdk.ModifierType.MOD1_MASK
            return event
        return True
    return False


class List(Tuple):
    def __init__(self, substruct, *args, **kwargs):
        super().__init__([substruct], *args, **kwargs)
        self._substruct = substruct

    def _get_nth_substruct(self, n):
        return self._substruct

    def _list_substruct_value(self, value):
        return ((self._substruct, subvalue) for subvalue in value or [None])

    def _key_press(self, row, index, event):
        return _list_key_press(row, index, event, self._substruct)


class TupleAndList(Tuple):
    def __init__(self, substructs, *args, **kwargs):
        super().__init__(substructs, *args, **kwargs)
        self.N = len(substructs) - 1
        self._list_substruct = substructs[-1]

    def _get_nth_substruct(self, n):
        return self._substructs[n] if n < self.N else self._list_substruct

    def _list_substruct_value(self, value):
        return Tuple._list_substruct_value(self, value[:self.N] + value[self.N] if value else None)

    def _get_value(self, row):
        value = Tuple._get_value(self, row)
        return value[:self.N] + [value[self.N:]]

    def _key_press(self, row, index, event):
        return _list_key_press(row, index, event, self._list_substruct, self.N)
