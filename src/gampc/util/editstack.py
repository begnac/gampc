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


class Delta:
    def __init__(self, items, position, push):
        self.items = items
        self.position = position
        self.push = push

    def apply(self, push, add_cb, remove_cb):
        "Return item: focus position (or None), selection list."
        if not self.push:
            push = not push
        if push:
            add_cb(self.position, self.items)
            return self.position, list(range(self.position, self.position + len(self.items)))
        else:
            remove_cb(self.position, len(self.items))
            return self.position, []

    def transpose_position_after(self, position, push=True):
        if position < self.position:
            return position
        if not self.push:
            push = not push
        n = len(self.items)
        if push:
            return position + n
        else:
            assert position >= self.position + n
            return position - n

    def transpose_self_after(self, deltas):
        for delta in deltas:
            self.position = delta.transpose_position_after(self.position)


class Transaction:
    def __init__(self):
        self.deltas = []

    def append(self, delta):
        delta.transpose_self_after(self.deltas)
        self.deltas.append(delta)

    def apply(self, push, add_cb, remove_cb):
        focus = None
        selection = []
        for delta in self.deltas if push else reversed(self.deltas):
            new_focus, new_selection = delta.apply(push, add_cb, remove_cb)
            focus = delta.transpose_position_after(focus, push) if focus is not None else new_focus
            selection = [delta.transpose_position_after(position, push) for position in selection] + new_selection
        return focus, selection


class EditStack:
    def __init__(self, items):
        self.hold_counter = 0
        self.reset()
        self.splicer = None
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

    def step(self, push):
        if self.hold_counter > 0:
            return RuntimeError
        if not push:
            self.index -= 1
        focus, selection = self.transactions[self.index].apply(push, self._add_cb, self._remove_cb)
        if push:
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
        if self.hold_counter == 0:
            raise RuntimeError
        self.transaction.append(delta)

    def set_splicer(self, splicer=None, step_cb=None):
        self.splicer = splicer
        self.step_cb = step_cb
        if splicer is not None:
            splicer(0, None, self.items)

    def _add_cb(self, pos, items):
        self.items[pos:pos] = items
        if self.splicer:
            self.splicer(pos, 0, items)

    def _remove_cb(self, pos, n):
        self.items[pos:pos + n] = []
        if self.splicer:
            self.splicer(pos, n, [])
