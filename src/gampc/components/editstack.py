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
from gi.repository import Gtk

import ampd
import asyncio

from .. import util
from ..ui import dialog
from . import songlistbase


class SimpleDelta(GObject.Object):
    def __init__(self, strings, position, push):
        super().__init__()
        self.strings = strings
        self.position = position
        self.push = push

    def apply(self, push, add_cb, remove_cb):
        "Return value: focus position (or None), selection list."
        if not self.push:
            push = not push
        if push:
            add_cb(self.position, self.strings)
            return self.position, list(range(self.position, self.position + len(self.strings)))
        else:
            # if model[self.position:self.position + len(self.strings)] != self.strings:
            #     raise RuntimeError
            remove_cb(self.position, len(self.strings))
            pos = self.position
            # if pos == len(model):
            #     pos -= 1
            if pos >= 0:
                return pos, [pos]
            else:
                return None, []

    def translate_positions(self, positions, push):
        if not self.push:
            push = not push
        if push:
            return [pos + len(self.strings) if pos >= self.position else pos for pos in positions]
        else:
            return [pos - len(self.strings) if pos >= self.position else pos for pos in positions]


class MetaDelta(GObject.Object):
    def __init__(self, deltas, push):
        super().__init__()
        if not deltas:
            raise RuntimeError
        self.deltas = deltas
        self.push = push

    def apply(self, push, add_cb, remove_cb):
        if not self.push:
            push = not push
        focus = None
        add_selection = []
        remove_selection = []
        for delta in self.deltas if push else reversed(self.deltas):
            focus, new_selection = delta.apply(push, add_cb, remove_cb)
            add_selection = delta.translate_positions(add_selection, push)
            remove_selection = delta.translate_positions(remove_selection, push)
            if push == delta.push:
                add_selection += new_selection
            else:
                remove_selection += new_selection
        return focus, add_selection or remove_selection

    def translate_positions(self, positions, push):
        if not self.push:
            push = not push
        for delta in self.deltas if push else reversed(self.deltas):
            positions = delta.translate_pos(positions, push)
        return positions


class EditStack:
    def __init__(self, strings):
        self.reset()
        self.target = None

        self.strings = strings

    def step(self, push):
        if not push:
            self.pos -= 1
        focus, selection = self.deltas[self.pos].apply(push, self.add_cb, self.remove_cb)
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

    def set_target(self, target=None):
        self.target = target
        if target is not None:
            target.set_items(self.strings)

    def add_cb(self, pos, strings):
        self.strings[pos:pos] = strings
        if self.target:
            self.target.splice_items(pos, 0, strings)

    def remove_cb(self, pos, n):
        self.strings[pos:pos + n] = []
        if self.target:
            self.target.splice_items(pos, n, [])


class SongListBaseEditStackMixin(songlistbase.SongListBaseEditableMixin):
    def __init__(self, unit, *args, **kwargs):
        super().__init__(unit, *args, **kwargs)
        self.songlistbase_actions.add_action(util.resource.Action('save', self.action_save_cb))
        # self.songlistbase_actions.add_action(util.resource.Action('reset', self.action_reset_cb))
        self.songlistbase_actions.add_action(util.resource.Action('undo', self.action_do_cb))
        self.songlistbase_actions.add_action(util.resource.Action('redo', self.action_do_cb))

        self.edit_stack = None

        # self.view.item_edited_hooks.append(self.item_edited_hook)

    # def shutdown(self):
    #     super().shutdown()
    #     self.view.item_edited_hooks.remove(self.item_edited_hook)

    # def item_edited_hook(self, item, key, value):
    #     new_item = util.item.Item(item.get_data())
    #     if value:
    #         new_item[key] = value
    #     else:
    #         del new_item[key]
    #     position = list(self.view.item_selection).index(item)
    #     delta1 = SimpleDelta([item], position, False)
    #     delta2 = SimpleDelta([new_item], position, True)
    #     self.edit_stack.set_from_here([MetaDelta([delta1, delta2], True)])
    #     self.step_edit_stack(True)

    def set_edit_stack(self, edit_stack):
        if self.edit_stack is not None:
            self.edit_stack.set_target()
        self.edit_stack = edit_stack
        if edit_stack is not None:
            self.edit_stack.set_target(self.view.item_store)
        else:
            self.view.item_store.remove_all()

    def step_edit_stack(self, push):
        focus, selection = self.edit_stack.step(push)
        if focus is not None:
            self.view.item_view.scroll_to(focus, None, Gtk.ListScrollFlags.FOCUS, None)
        if selection is not None:
            self.view.item_selection.unselect_all()
            for pos in selection:
                self.view.item_selection.select_item(pos, False)
        self.edit_stack_changed()

    def remove_items(self, items):
        if not items:
            return
        indices = []
        for i, item in enumerate(self.view.item_selection):
            if item in items:
                indices.append(i)
                items.remove(item)
        if items:
            raise RuntimeError
        deltas = []
        i = j = indices[0]
        for k in indices[1:] + [0]:
            j += 1
            if j != k:
                deltas.append(SimpleDelta(self.view.item_selection[i:j], i, True))
                i = j = k
        self.edit_stack.set_from_here([MetaDelta(deltas, False)])
        self.step_edit_stack(True)

    def add_items(self, strings, position):
        if not strings:
            return
        self.edit_stack.set_from_here([SimpleDelta(strings, position, True)])
        self.step_edit_stack(True)

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
