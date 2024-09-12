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

from ..control import compound

from . import mixins


class __unit__(mixins.UnitComponentMixin, mixins.UnitServerMixin, unit.Unit):
    TITLE = _("Execute MPD commands")
    KEY = '7'

    def new_widget(self):
        return compound.WidgetWithEntry(Gtk.Label(max_width_chars=50, wrap=True, selectable=True, vexpand=True), self.entry_activate_cb)

    @ampd.task
    async def entry_activate_cb(self, entry, label):
        reply = await self.ampd._raw(entry.get_text())
        label.set_label('\n'.join(str(x) for x in reply) if reply else _("Empty reply"))
