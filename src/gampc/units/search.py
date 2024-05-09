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


import ampd

from .. import util
from ..components import component
from ..components import songlist


class Search(component.ComponentEntryMixin, songlist.SongList):
    duplicate_test_columns = ['Title', 'Artist', 'Performer', 'Date']

    sortable = True

    def __init__(self, unit):
        super().__init__(unit)

        # self.field_choice = Gtk.ComboBoxText()
        # self.field_choice.append_text(_("any field"))
        # for name in self.fields.names:
        #     self.field_choice.append_text(name)

        self.actions.add_action(util.resource.Action('search', self.action_search_cb))

    def action_search_cb(self, *args):
        self.entry.grab_focus()

    @ampd.task
    async def client_connected_cb(self, client):
        while True:
            self.entry.activate()
            await self.ampd.idle(ampd.DATABASE)

    def action_reset_cb(self, action, parameter):
        super().action_reset_cb(action, parameter)
        self.field_choice.set_active(0)
        self.entry.activate()

    @ampd.task
    async def entry_activate_cb(self, entry):
        query = entry.get_text()
        if not query:
            return
        if query[0] == '!':
            query = query[1:]
            find = True
        else:
            find = False
        condition = sum((['any', s] if '=' not in s else s.split('=', 1) for s in self.parse(query)), [])
        if condition:
            songs = await (self.ampd.find if find else self.ampd.search)(*condition)
            self.set_songs(song['file'] for song in songs)

    @staticmethod
    def parse(s):
        token = None
        for c in s:
            if token is None:
                if c.isspace():
                    continue
                else:
                    token = ''
                    quote = False
                    escape = False
            if escape:
                token += c
                escape = False
            elif c == '\\':
                escape = True
            elif c == '"':
                quote = not quote
            elif c.isspace() and not quote:
                yield token
                token = None
            else:
                token += c
        if token is not None:
            if quote:
                raise ValueError(_("Unbalanced quotes"))
            yield token


@util.unit.require_units('misc')
class __unit__(songlist.UnitSongListMixin, util.unit.UnitDatabaseMixin, util.unit.Unit):
    title = _("Search")
    key = '3'

    COMPONENT_CLASS = Search

    def __init__(self, name, manager):
        super().__init__(name, manager)
        self.add_resources(
            'app.menu',
            util.resource.MenuAction('edit/component', 'search.search', _("Search"), ['<Control><Alt>f']),
        )
