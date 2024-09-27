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

from ..util import action
from ..util import item
from ..util import unit

from ..view.cache import ViewCacheWithCopy

from ..control import compound

from . import mixins


class SearchWidget(compound.WidgetWithEntry):
    def __init__(self, fields, cache, separator_file, activate_cb, **kwargs):
        view = ViewCacheWithCopy(fields=fields, cache=cache, sortable=True)
        super().__init__(view, activate_cb, **kwargs)
        view.add_context_menu_actions(self.generate_actions(), 'search', _("Search"))
        item.setup_find_duplicate_items(view.item_model, ['Title', 'Artist', 'Performer', 'Date'], [separator_file])
        self.add_cleanup_below(view)

        # self.field_choice = Gtk.ComboBoxText()
        # self.field_choice.append_text(_("any field"))
        # for name in self.fields.names:
        #     self.field_choice.append_text(name)

    def generate_actions(self):
        yield action.ActionInfo('search', self.action_search_cb, _("Search"), ['<Control><Alt>f'])

    def action_search_cb(self, *args):
        self.entry.grab_focus()

    # def action_reset_cb(self, action, parameter):
    #     super().action_reset_cb(action, parameter)
    #     self.field_choice.set_active(0)
    #     self.entry.activate()


class __unit__(mixins.UnitComponentQueueActionMixin, unit.Unit):
    TITLE = _("Search")
    KEY = '3'

    def __init__(self, manager):
        super().__init__(manager)
        self.require('database')
        self.require('fields')
        self.require('persistent')

    def new_widget(self):
        search = SearchWidget(self.unit_fields.fields, self.unit_database.cache, self.unit_database.SEPARATOR_FILE, self.entry_activate_cb)
        search.connect_clean(self.unit_server.ampd_client, 'client-connected', self.search_client_connected_cb, search)

        search.main.add_context_menu_actions(self.generate_queue_actions(search.main), 'queue', self.TITLE, protect=self.unit_persistent.protect, prepend=True)
        search.connect_clean(search.main.item_view, 'activate', self.view_activate_cb)
        return search

    @ampd.task
    async def search_client_connected_cb(self, client, search):
        while True:
            search.entry.activate()
            await self.ampd.idle(ampd.DATABASE)

    @ampd.task
    async def entry_activate_cb(self, entry, view):
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
            self.unit_database.update(songs)
            view.item_model.set_values(songs)

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
