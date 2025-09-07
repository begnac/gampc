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


import asyncio
import decorator

from gi.repository import Gdk
from gi.repository import Gtk


class Rectangle(Gdk.Rectangle):
    def __init__(self, x, y, width=0, height=0):
        self.x = x
        self.y = y
        self.width = width
        self.height = height


def format_time(time):
    time = int(time)
    hours = time // 3600
    minutes = (time // 60) % 60
    seconds = time % 60
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes:02}:{seconds:02}"


def get_display():
    return Gdk.Display.get_default()


def get_modifier_state():
    return get_display().get_default_seat().get_keyboard().get_modifier_state()


def get_clipboard():
    return get_display().get_clipboard()


def find_descendant_at_xy(widget, x, y, levels):
    child = widget.pick(x, y, Gtk.PickFlags(0))
    pile = []
    while child != widget:
        if child is None:
            return None, x, y
        pile.append(child)
        child = child.get_parent()
    for child in reversed(pile):
        if levels == 0:
            break
        x, y = widget.translate_coordinates(child, x, y)
        widget = child
        levels -= 1
    if levels:
        widget = None
    return widget, x, y


def get_selection(selection):
    found, i, pos = Gtk.BitsetIter.init_first(selection.get_selection())
    while found:
        yield pos
        found, pos = i.next()


def add_unique_css_class(widget, prefix, suffix):
    for css_class in widget.get_css_classes():
        if css_class.startswith(prefix):
            widget.remove_css_class(css_class)
    if suffix is not None:
        widget.add_css_class(f'{prefix}-{suffix}')


@decorator.decorator
def create_task(coro, *args, **kwargs):
    return asyncio.create_task(coro(*args, **kwargs), name=coro.__name__)


def prepend_mixin(mixin, extra={}):
    def prepender(cls):
        return type(cls.__name__, (mixin, cls,), extra)
    return prepender


class FactoryBase(Gtk.SignalListItemFactory):
    def __init__(self):
        super().__init__()
        self.connect('setup', self.__class__.setup_cb)
        self.connect('bind', self.__class__.bind_cb)
        self.connect('unbind', self.__class__.unbind_cb)
        self.connect('teardown', self.__class__.teardown_cb)

    def setup_cb(self, listitem):
        pass

    def bind_cb(self, listitem):
        pass

    def unbind_cb(self, listitem):
        pass

    def teardown_cb(self, listitem):
        pass


# class DebugTime:
#     import sys
#     import time as time

#     def __init__(self):
#         self.last_time = self.time.time()
#         self.n_last_time = 0

#     def run(self):
#         self.n_last_time += 1
#         now = self.time.time()
#         print(f"{self.sys._getframe().f_back.f_code.co_name}: {self.n_last_time}, {now - self.last_time}")
#         self.last_time = now


# debug_time = DebugTime()
