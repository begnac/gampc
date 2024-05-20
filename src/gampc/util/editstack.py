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


class SimpleDelta:
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
            return [pos + len(self.items) if pos >= self.position else pos for pos in positions]
        else:
            return [pos - len(self.items) if pos >= self.position else pos for pos in positions]


class MetaDelta:
    def __init__(self, deltas, push):
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
    def __init__(self, items):
        self.reset()
        self.splicer = None
        self.items = items

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

    def set_splicer(self, splicer=None):
        self.splicer = splicer
        if splicer is not None:
            splicer(0, None, self.items)

    def add_cb(self, pos, items):
        self.items[pos:pos] = items
        if self.splicer:
            self.splicer(pos, 0, items)

    def remove_cb(self, pos, n):
        self.items[pos:pos + n] = []
        if self.splicer:
            self.splicer(pos, n, [])
