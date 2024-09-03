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
from ..util import cleanup
from ..util import item
from ..util import misc
from ..util import unit

from ..ui import compound

from ..view.cache import ViewCacheWithCopy

from ..components import component

from . import mixins


class SearchWidget(misc.UseAMPDMixin, compound.WidgetWithEntry):
    def __init__(self, fields, cache, separator_file, activate_cb, **kwargs):
        view = ViewCacheWithCopy(fields=fields, cache=cache)
        super().__init__(view, activate_cb, **kwargs)
        view.add_to_context_menu(self.generate_actions(), 'search', _("Search"))
        item.setup_find_duplicate_items(view.item_store, ['Title', 'Artist', 'Performer', 'Date'], [separator_file])

        # self.field_choice = Gtk.ComboBoxText()
        # self.field_choice.append_text(_("any field"))
        # for name in self.fields.names:
        #     self.field_choice.append_text(name)

    def generate_actions(self):
        yield action.ActionInfo('search', self.action_search_cb, _("Search"), ['<Control><Alt>f'])

    def action_search_cb(self, *args):
        self.entry.grab_focus()

    @ampd.task
    async def client_connected_cb(self):
        while True:
            self.entry.activate()
            await self.ampd.idle(ampd.DATABASE)

    # def action_reset_cb(self, action, parameter):
    #     super().action_reset_cb(action, parameter)
    #     self.field_choice.set_active(0)
    #     self.entry.activate()


class __unit__(mixins.UnitComponentQueueActionMixin, mixins.UnitServerMixin, unit.Unit):
    TITLE = _("Search")

    def __init__(self, *args):
        super().__init__(*args)
        self.require('database')
        self.require('fields')
        self.require('persistent')
        self.require('component')

        self.unit_component.register_component(self.name, self.TITLE, '3', self.new_instance)

    def cleanup(self):
        self.unit_component.unregister_component(self.name)
        super().cleanup()

    def new_instance(self):
        search = SearchWidget(self.unit_fields.fields, self.unit_database.cache, self.unit_database.SEPARATOR_FILE, self.entry_activate_cb, ampd=self.ampd)
        search.connect_clean(search.entry, 'activate', self.entry_activate_cb, search.main)
        search.connect_clean(search.main.item_view, 'activate', self.view_activate_cb)
        return component.ComponentWidget(search, subtitle=self.TITLE)

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
            view.set_values(songs)

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
