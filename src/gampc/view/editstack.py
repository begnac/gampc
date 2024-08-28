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

import asyncio

from ..util import action
from ..util import editstack

from ..ui import dialog

from .actions import ViewWithCopyPaste


class ViewWithEditStack(ViewWithCopyPaste):
    __gsignals__ = {
        'edit-stack-changed': (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.edit_stack = None
        self.add_to_context_menu(self.generate_edit_stack_actions(), 'edit-stack', _("Edit stack"))
        self.edit_stack_changed()

    def cleanup(self):
        self.set_edit_stack(None)
        super().cleanup()

    def generate_edit_stack_actions(self):
        # yield action.ActionInfo('save', self.action_save_cb, _("Save"), ['<Control>s'])
        yield action.ActionInfo('reset', self.action_reset_cb, _("Reset"), ['<Control>r'])
        yield action.ActionInfo('undo', self.action_do_cb, _("Undo"), ['<Control>z'], parameter_format='b', arg=False)
        yield action.ActionInfo('redo', self.action_do_cb, _("Redo"), ['<Shift><Control>z'], parameter_format='b', arg=True)
        # util.resource.MenuAction('edit/songlist/base', 'itemlist.undelete', _("Undelete"), ['<Alt>Delete'], accels_fragile=True),

    def action_do_cb(self, action, parameter):
        self.step_edit_stack(parameter.unpack())
        self.edit_stack_changed()

    def action_reset_cb(self, action, parameter):
        asyncio.create_task(self.reset())

    async def reset(self):
        if not self.edit_stack or not self.edit_stack.deltas:
            return
        if not await dialog.MessageDialogAsync(transient_for=self.get_root(), message=_("Reset and lose all modifications?")).run():
            return
        self.edit_stack.undo()
        self.edit_stack.reset()
        self.edit_stack_changed()

    def set_edit_stack(self, edit_stack):
        if self.edit_stack is not None:
            self.edit_stack.set_splicer()
        self.edit_stack = edit_stack
        if edit_stack is not None:
            self.edit_stack.set_splicer(self.edit_stack_splicer)
        else:
            self.item_store.remove_all()

    def step_edit_stack(self, push):
        focus, selection = self.edit_stack.step(push)
        self.refocus(focus, selection)

    def refocus(self, focus, selection):
        if focus is not None:
            self.item_view.scroll_to(focus, None, Gtk.ListScrollFlags.FOCUS, None)
        if selection is not None:
            self.item_selection_model.unselect_all()
            for pos in selection:
                self.item_selection_model.select_item(pos, False)
        self.edit_stack_changed()

    def remove_positions(self, positions):
        if not positions:
            return
        # indices = []
        # for i, item_ in enumerate(self.item_selection_model):
        #     if item_ in items:
        #         indices.append(i)
        #         items.remove(item_)
        # if items:
        #     raise RuntimeError
        deltas = []
        i = j = positions[0]
        for k in positions[1:] + [0]:
            j += 1
            if j != k:
                values = [self.edit_stack_getter(item) for item in self.item_selection_model[i:j]]
                deltas.append(editstack.SimpleDelta(values, i, True))
                i = j = k
        self.edit_stack.set_from_here([editstack.MetaDelta(deltas, False)])
        self.step_edit_stack(True)

    def add_items(self, values, position):
        if not values:
            return
        self.edit_stack.set_from_here([editstack.SimpleDelta(values, position, True)])
        self.step_edit_stack(True)

    def edit_stack_changed(self):
        self.emit('edit-stack-changed')
        # self.actions['edit-stack'].lookup_action('save').set_enabled(True)
        self.actions['edit-stack'].lookup_action('undo').set_enabled(self.edit_stack and self.edit_stack.pos > 0)
        self.actions['edit-stack'].lookup_action('redo').set_enabled(self.edit_stack and self.edit_stack.pos < len(self.edit_stack.deltas))
