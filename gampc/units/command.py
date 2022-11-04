# coding: utf-8
#
# Graphical Asynchronous Music Player Client
#
# Copyright (C) 2015-2022 Itaï BEN YAACOV
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

import ampd

from ..util import unit
from ..components import component


class Command(component.Component):
    title = _("Execute MPD commands")
    name = 'command'
    key = '7'

    def __init__(self, *args):
        super().__init__(*args)
        self.label = Gtk.Label(max_width_chars=50, wrap=True, selectable=True, visible=True)
        self.entry = Gtk.Entry(visible=True)
        self.entry.connect('activate', self.entry_activate_cb)
        self.entry.connect('focus-in-event', self.entry_focus_cb)
        self.entry.connect('focus-out-event', self.entry_focus_cb)
        scrolled = Gtk.ScrolledWindow(visible=True)
        scrolled.add(self.label)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=True)
        box.pack_start(scrolled, True, True, 0)
        box.pack_end(self.entry, False, False, 0)
        self.add(box)
        self.connect('map', lambda self: self.entry.grab_focus())

    @ampd.task
    async def entry_activate_cb(self, entry):
        reply = await self.ampd._raw(entry.get_text())
        self.label.set_label('\n'.join(str(x) for x in reply) if reply else _("Empty reply"))

    def entry_focus_cb(self, entry, event):
        self.unit.unit_misc.block_fragile_accels = event.in_
        return False


class __unit__(component.UnitMixinComponent, unit.Unit):
    REQUIRED_UNITS = ['misc']
    MODULE_CLASS = Command
