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


import weakref


class DeltaSplicer:
    def __init__(self, items, position, advance, splicer):
        self.items = items
        self.position = position
        self.advance = advance
        self.splicer = splicer

    def apply(self, advance):
        if not self.advance:
            advance = not advance
        if advance:
            self.splicer(self.position, 0, self.items)
            return self.position, list(range(self.position, self.position + len(self.items)))
        else:
            self.splicer(self.position, len(self.items), [])
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
    def __init__(self, item, key, new):
        self.item = weakref.ref(item)  # Otherwise cleanup is very difficult
        self.key = key
        self.old = item.value.get(key)
        self.new = new

    def apply(self, advance):
        if advance:
            old, new = self.old, self.new
        else:
            old, new = self.new, self.old
        item = self.item()
        assert item is not None and item.value.get(self.key) == old
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
    def __init__(self):
        self.deltas = []

    def append(self, delta):
        delta.transpose_self_after(self.deltas)
        self.deltas.append(delta)

    def apply(self, advance):
        focus = None
        selection = []
        for delta in self.deltas if advance else reversed(self.deltas):
            new_focus, new_selection = delta.apply(advance)
            focus = delta.transpose_position_after(focus, advance) if focus is not None else new_focus
            selection = [delta.transpose_position_after(position, advance) for position in selection] + new_selection
        return focus, selection


class EditStack:
    def __init__(self, items):
        self.hold_counter = 0
        self.reset()
        self.step_cb = None
        self.items = items

    def reset(self):
        if self.hold_counter > 0:
            return RuntimeError
        self.transactions = []
        self.index = 0

    def undo(self):
        if self.hold_counter > 0:
            return RuntimeError
        while self.index:
            self.step(False)

    def step(self, advance):
        if self.hold_counter > 0:
            return RuntimeError
        if not advance:
            self.index -= 1
        focus, selection = self.transactions[self.index].apply(advance)
        if advance:
            self.index += 1
        if self.step_cb:
            self.step_cb(focus, selection)

    def hold_transaction(self):
        if self.hold_counter == 0:
            self.transactions = self.transactions[:self.index]
            self.transaction = Transaction()
        self.hold_counter += 1

    def release_transaction(self):
        if self.hold_counter == 0:
            raise RuntimeError
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

    def set_step_cb(self, step_cb=None):
        self.step_cb = step_cb
