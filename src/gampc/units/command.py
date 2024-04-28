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

import ampd

from ..util import unit
from ..components import component


class _Command(component.Component):
    def __init__(self, unit):
        super().__init__(unit)
        self.label = Gtk.Label(max_width_chars=50, wrap=True, selectable=True)
        self.widget = scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_child(self.label)

    @ampd.task
    async def entry_activate_cb(self, entry):
        reply = await self.ampd._raw(entry.get_text())
        self.label.set_label('\n'.join(str(x) for x in reply) if reply else _("Empty reply"))


class Command(component.ComponentEntryMixin, _Command):
    pass


class __unit__(component.UnitComponentMixin, unit.Unit):
    title = _("Execute MPD commands")
    key = '7'

    COMPONENT_CLASS = Command

    def required_units(self):
        yield from super().required_units()
        yield 'misc'
