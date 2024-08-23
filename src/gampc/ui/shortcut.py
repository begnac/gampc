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


from gi.repository import Gtk

from .. import util


def get_accel_trigger(accel):
    parsed, keyval, modifiers = Gtk.accelerator_parse(accel)
    if not parsed:
        raise ValueError(accel)
    return Gtk.KeyvalTrigger(keyval=keyval, modifiers=modifiers)


def get_accels_trigger(accels):
    trigger = get_accel_trigger(accels[0])
    for accel in accels[1:]:
        trigger = Gtk.AlternativeTrigger(first=trigger, second=get_accel_trigger(accel))
    return trigger


class Accel:
    def __init__(self, title, accels, action, arguments=None):
        self.title = title
        self.accels = accels
        self.action = action
        self.arguments = arguments


class ShortcutAggregator(util.resource.ResourceAggregator):
    def __init__(self, sources, title):
        super().__init__(sources)
        self.controller = ShortcutController(title)

    def add_resource(self, source, accel):
        super().add_resource(source, accel)
        self.controller.add_accel(accel)

    def remove_resource(self, source, accel):
        self.controller.remove_accel(accel)
        super().remove_resource(source, accel)


class ShortcutController(Gtk.ShortcutController):
    def __init__(self, title):
        super().__init__()
        self.title = title
        self.accels = {}

    def add_accel(self, accel):
        if accel in self.accels:
            raise KeyError
        shortcut = Gtk.Shortcut(trigger=get_accels_trigger(accel.accels), action=Gtk.NamedAction.new(accel.action), arguments=accel.arguments)
        self.accels[accel] = shortcut
        self.add_shortcut(shortcut)

    def remove_accel(self, accel):
        self.remove_shortcut(self.accels.pop(accel))
