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

from ..util import action
from ..util import editstack
from ..util import misc

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
        del self.edit_stack
        super().cleanup()

    def generate_edit_stack_actions(self):
        yield action.ActionInfo('undo', self.action_do_cb, _("Undo"), ['<Control>z'], arg=False, arg_format='b')
        yield action.ActionInfo('redo', self.action_do_cb, _("Redo"), ['<Shift><Control>z'], arg=True, arg_format='b')
        yield action.ActionInfo('reset', self.action_reset_cb, _("Reset"), ['<Control>r'])

    def action_do_cb(self, action, parameter):
        self.edit_stack.step(parameter.unpack())

    @misc.create_task
    async def action_reset_cb(self, action, parameter):
        if not self.edit_stack or not self.edit_stack.transactions:
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
            self.edit_stack.set_splicer(self.edit_stack_splicer, self.step_cb)
        else:
            self.item_model.remove_all()
        self.edit_stack_changed()

    def step_cb(self, focus, selection):
        self.refocus(focus, selection)
        self.edit_stack_changed()

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
        self.edit_stack.hold_transaction()
        i = j = positions[0]
        for k in positions[1:] + [0]:
            j += 1
            if j != k:
                values = [self.edit_stack_getter(item) for item in self.item_selection_model[i:j]]
                self.edit_stack.append_delta(editstack.Delta(values, i, False))
                i = j = k
        self.edit_stack.release_transaction()

    def add_items(self, values, position):
        if not values:
            return
        self.edit_stack.hold_transaction()
        self.edit_stack.append_delta(editstack.Delta(values, position, True))
        self.edit_stack.release_transaction()

    def edit_stack_changed(self):
        self.emit('edit-stack-changed')
        self.actions['edit-stack'].lookup_action('undo').set_enabled(self.edit_stack and self.edit_stack.index > 0)
        self.actions['edit-stack'].lookup_action('redo').set_enabled(self.edit_stack and self.edit_stack.index < len(self.edit_stack.transactions))

    def lock(self):
        self.edit_stack.hold_transaction()

    def unlock(self):
        self.edit_stack.release_transaction()
