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

import weakref

from ..util import action
from ..util import misc


class DeltaSplicer:
    def __init__(self, position, items, advance):
        self.position = position
        self.items = items
        self.advance = advance

    def apply(self, advance, edit_stack):
        if not self.advance:
            advance = not advance
        if advance:
            edit_stack.splice(self.position, 0, self.items)
            return self.position, list(range(self.position, self.position + len(self.items)))
        else:
            edit_stack.splice(self.position, len(self.items), [])
            return self.position, []

    def transpose_position_after(self, position, advance=True):
        if position < self.position:
            return position
        if not self.advance:
            advance = not advance
        n = len(self.items)
        if advance:
            return position + n
        else:
            assert position >= self.position + n
            return position - n

    def transpose_self_after(self, deltas):
        for delta in deltas:
            self.position = delta.transpose_position_after(self.position)


class DeltaItem:
    def __init__(self, key, old, new):
        self.key = key
        self.old = old
        self.new = new

    def apply(self, advance, edit_stack):
        if advance:
            old, new = self.old, self.new
        else:
            old, new = self.new, self.old
        item = edit_stack.get_item()
        assert item.value.get(self.key) == old
        value = dict(item.value)
        if new is not None:
            value[self.key] = new
        elif old is not None:
            del value[self.key]
        item.value = value
        return None, []

    def transpose_position_after(self, position, advance=True):
        return position

    def transpose_self_after(self, deltas):
        return


class Transaction:
    def __init__(self, *, deltas=None, advance=True):
        self.deltas = [] if deltas is None else deltas
        self.advance = advance

    def append(self, delta):
        delta.transpose_self_after(self.deltas)
        self.deltas.append(delta)

    def apply(self, advance, edit_stack):
        focus = None
        selection = []
        if not self.advance:
            advance = not advance
        for delta in self.deltas if advance else reversed(self.deltas):
            new_focus, new_selection = delta.apply(advance, edit_stack)
            focus = delta.transpose_position_after(focus, advance) if focus is not None else new_focus
            selection = [delta.transpose_position_after(position, advance) for position in selection] + new_selection
        return focus, selection

    def reverse(self):
        return Transaction(deltas=self.deltas, advance=not self.advance)


class EditStack(GObject.Object):
    __gsignals__ = {
        'splice': (GObject.SIGNAL_RUN_FIRST, None, (int, int, int)),
        'step': (GObject.SIGNAL_RUN_FIRST, None, (object, object)),
    }

    modified = GObject.Property(type=bool, default=False)

    def __init__(self, items=None, item=None):
        super().__init__()
        self.hold_counter = 0
        self.reset()
        self.items = items or []
        if item is not None:
            self.item = weakref.ref(item)

    def reset(self):
        assert self.hold_counter == 0
        self.transactions = []
        self.index = self.base = 0
        self.modified = False

    def rebase(self):
        assert self.hold_counter == 0
        self.base = self.index
        self.modified = False

    def to_base(self):
        assert self.hold_counter == 0
        while self.index != self.base:
            self.step(self.index < self.base)

    def get_item(self):
        return self.item()

    def splice(self, p, r, a):
        assert self.hold_counter == 0
        self.items[p:p + r] = a
        self.emit('splice', p, r, len(a))

    def step(self, advance):
        assert self.hold_counter == 0
        if not advance:
            assert self.index > 0
            self.index -= 1
        focus, selection = self.transactions[self.index].apply(advance, self)
        if advance:
            assert self.index < len(self.transactions)
            self.index += 1
        modified = self.index != self.base
        if modified != self.modified:
            self.modified = modified
        self.emit('step', focus, selection)

    def hold_transaction(self):
        if self.hold_counter == 0:
            if self.base <= self.index:
                self.transactions = self.transactions[:self.index]
            else:
                self.transactions = self.transactions[:self.base]
                for transaction in reversed(self.transactions[self.index:self.base]):
                    self.transactions.append(transaction.reverse())
                self.index = len(self.transactions)
            self.transaction = Transaction()
        self.hold_counter += 1

    def release_transaction(self):
        assert self.hold_counter > 0
        self.hold_counter -= 1
        if self.hold_counter == 0:
            if self.transaction.deltas:
                self.transactions.append(self.transaction)
                self.step(True)
            del self.transaction

    def append_delta(self, delta):
        self.hold_transaction()
        self.transaction.append(delta)
        self.release_transaction()


class WidgetEditStackMixin:
    def __init__(self, *args, edit_stack_view=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.edit_stack = None
        family = action.ActionInfoFamily(self.generate_edit_stack_actions(), 'edit-stack', _("Edit stack"))
        self.edit_stack_menu = family.get_menu()
        self.edit_stack_actions = family.get_action_group()
        if edit_stack_view is not None:
            edit_stack_view.remove_positions = self.remove_positions
            edit_stack_view.add_items = self.add_items
            edit_stack_view.lock = self.lock
            edit_stack_view.unlock = self.unlock
            self.edit_stack_view = edit_stack_view
        else:
            self.edit_stack_view = self
        self.insert_action_group('edit-stack', self.edit_stack_actions)
        self.add_controller(family.get_shortcut_controller())
        self.edit_stack_changed()

    def cleanup(self):
        self.insert_action_group('edit-stack', None)
        del self.edit_stack_actions
        if self.edit_stack_view is self:
            del self.edit_stack_view
        else:
            del self.edit_stack_view.remove_positions
            del self.edit_stack_view.add_items
            del self.edit_stack_view.lock
            del self.edit_stack_view.unlock
        del self.edit_stack
        super().cleanup()

    def generate_edit_stack_actions(self):
        yield action.ActionInfo('undo', self.action_do_cb, _("Undo"), ['<Control>z'], arg=False, arg_format='b')
        yield action.ActionInfo('redo', self.action_do_cb, _("Redo"), ['<Shift><Control>z'], arg=True, arg_format='b')
        yield action.ActionInfo('reset', self.action_reset_cb, _("Reset"), ['<Control>r'])
        yield action.ActionInfo('save', self.action_save_cb, _("Save"), ['<Control>s'])

    def action_do_cb(self, action, parameter):
        self.edit_stack.step(parameter.unpack())

    @misc.create_task
    async def action_reset_cb(self, action, parameter):
        assert self.edit_stack and self.edit_stack.transactions
        self.edit_stack.to_base()
        self.edit_stack_changed()

    action_save_cb = NotImplemented

    def set_edit_stack(self, edit_stack):
        if self.edit_stack is not None:
            self.edit_stack.disconnect_by_func(self.splice_cb)
            self.edit_stack.disconnect_by_func(self.step_cb)
        self.edit_stack_view.item_model.remove_all()
        self.edit_stack = edit_stack
        if edit_stack is not None:
            self.edit_stack_splicer(0, 0, self.edit_stack.items)
            self.edit_stack.connect('step', self.step_cb)
            self.edit_stack.connect('splice', self.splice_cb)
        self.edit_stack_changed()

    def step_cb(self, edit_stack, focus, selection):
        self.edit_stack_changed()
        self.refocus(focus, selection)

    def splice_cb(self, edit_stack, p, r, a):
        self.edit_stack_splicer(p, r, edit_stack.items[p:p + a])

    def refocus(self, focus, selection):
        if focus is not None:
            self.edit_stack_view.item_view.scroll_to(focus, None, 0, None)
        if selection is not None:
            self.edit_stack_view.item_selection_model.unselect_all()
            for pos in selection:
                self.edit_stack_view.item_selection_model.select_item(pos, False)

    def edit_stack_changed(self):
        self.edit_stack_actions.lookup_action('undo').set_enabled(self.edit_stack and self.edit_stack.index > 0)
        self.edit_stack_actions.lookup_action('redo').set_enabled(self.edit_stack and self.edit_stack.index < len(self.edit_stack.transactions))
        self.edit_stack_actions.lookup_action('reset').set_enabled(self.edit_stack and self.edit_stack.transactions)
        self.edit_stack_actions.lookup_action('save').set_enabled(self.edit_stack and self.edit_stack.index > 0)

    def remove_positions(self, positions):
        if not positions:
            return
        self.lock()
        i = j = positions[0]
        for k in positions[1:] + [0]:
            j += 1
            if j != k:
                values = self.edit_stack.items[i:j]
                self.edit_stack.append_delta(DeltaSplicer(i, values, False))
                i = j = k
        self.unlock()

    def add_items(self, position, values):
        if not values:
            return
        self.edit_stack.append_delta(DeltaSplicer(position, values, True))

    def lock(self):
        self.edit_stack.hold_transaction()

    def unlock(self):
        self.edit_stack.release_transaction()


class WidgetCacheEditStackMixin(WidgetEditStackMixin):
    def refocus(self, *args):
        self.edit_stack_view.aioqueue.queue_task(super().refocus, *args, sync=True)
