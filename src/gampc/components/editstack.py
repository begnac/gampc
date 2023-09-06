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


from gi.repository import GObject
from gi.repository import Gio
from gi.repository import Gtk

import ampd

from ..util import record
from ..util import resource
from ..util import dialog
from . import songlistbase


class SimpleDelta(GObject.Object):
    def __init__(self, records, position, push):
        super().__init__()
        self.records = records
        self.position = position
        self.push = push

    def apply(self, model, push):
        "Return value: focus position (or None), selection list."
        if not self.push:
            push = not push
        if push:
            model[self.position:self.position] = self.records
            return self.position, list(range(self.position, self.position + len(self.records)))
        else:
            if model[self.position:self.position + len(self.records)] != self.records:
                raise RuntimeError
            model[self.position:self.position + len(self.records)] = []
            pos = self.position
            if pos == len(model):
                pos -= 1
            if pos >= 0:
                return pos, [pos]
            else:
                return None, []

    def translate_positions(self, positions, push):
        if not self.push:
            push = not push
        if push:
            return [pos + len(self.records) if pos >= self.position else pos for pos in positions]
        else:
            return [pos - len(self.records) if pos >= self.position else pos for pos in positions]


class MetaDelta(GObject.Object):
    def __init__(self, deltas, push):
        super().__init__()
        if not deltas:
            raise RuntimeError
        self.deltas = deltas
        self.push = push

    def apply(self, model, push):
        if not self.push:
            push = not push
        focus = None
        selection = []
        for delta in self.deltas if push else reversed(self.deltas):
            focus, new_selection = delta.apply(model, push)
            selection = delta.translate_positions(selection, push) + new_selection
        return focus, selection

    def translate_positions(self, positions, push):
        if not self.push:
            push = not push
        for delta in self.deltas if push else reversed(self.deltas):
            positions = delta.translate_pos(positions, push)
        return positions


class EditStack:
    def __init__(self, records):
        self.records = Gio.ListStore(item_type=record.Record)
        self.records[:] = records
        self.reset()

    def step(self, push):
        if not push:
            self.pos -= 1
        focus, selection = self.deltas[self.pos].apply(self.records, push)
        if push:
            self.pos += 1
        return focus, selection

    def set_from_here(self, deltas):
        self.deltas[self.pos:] = deltas

    def undo(self):
        while self.pos:
            self.step(False)

    def reset(self):
        self.deltas = []
        self.pos = 0


class SongListBaseEditStackMixin(songlistbase.SongListBaseEditableMixin):
    def __init__(self, unit, *args, **kwargs):
        super().__init__(unit, *args, **kwargs)
        self.songlistbase_actions.add_action(resource.Action('save', self.action_save_cb))
        # self.songlistbase_actions.add_action(resource.Action('reset', self.action_reset_cb))
        self.songlistbase_actions.add_action(resource.Action('undo', self.action_do_cb))
        self.songlistbase_actions.add_action(resource.Action('redo', self.action_do_cb))

        self.edit_stack = None

    def shutdown(self):
        super().shutdown()
        self.set_edit_stack(None)

    @staticmethod
    def sync_records(source, p, r, a, target):
        target[p:p + r] = source[p:p + a]

    def set_edit_stack(self, edit_stack):
        if self.edit_stack is not None:
            self.edit_stack.records.disconnect_by_func(self.sync_records)
        self.edit_stack = edit_stack
        if edit_stack is not None:
            self.view.record_store[:] = edit_stack.records
            edit_stack.records.connect('items-changed', self.sync_records, self.view.record_store)

    def step_edit_stack(self, push):
        focus, selection = self.edit_stack.step(push)
        if focus is not None:
            self.view.record_view.scroll_to(focus, None, Gtk.ListScrollFlags.FOCUS, None)
        if selection is not None:
            self.view.record_selection.unselect_all()
            for pos in selection:
                self.view.record_selection.select_item(pos, False)
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
        self.edit_stack.set_from_here([MetaDelta(deltas, False)])
        self.step_edit_stack(True)

    def add_records(self, records, position):
        if not records:
            return
        self.edit_stack.set_from_here([SimpleDelta(records, position, True)])
        self.step_edit_stack(True)

    def add_records_from_data(self, data, position):
        self.add_records(self.records_from_data(data), position)

    def edit_stack_changed(self):
        self.songlistbase_actions.lookup_action('save').set_enabled(True)
        self.songlistbase_actions.lookup_action('undo').set_enabled(self.edit_stack and self.edit_stack.pos > 0)
        self.songlistbase_actions.lookup_action('redo').set_enabled(self.edit_stack and self.edit_stack.pos < len(self.edit_stack.deltas))

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
        if not await dialog.AsyncMessageDialog(transient_for=self.widget.get_root(), message=_("Reset and lose all modifications?")).run():
            return
        self.edit_stack.undo()
        self.edit_stack.reset()
        self.edit_stack_changed()
