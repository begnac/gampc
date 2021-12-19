# coding: utf-8
#
# Graphical Asynchronous Music Player Client
#
# Copyright (C) 2015 Itaï BEN YAACOV
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

import ast
import ampd

from gampc.util import ssde
from gampc.util import db
from gampc.util import resource
from gampc.util import component
from gampc.units import songlist


class SavedSearch(songlist.SongListWithEditDelFile, component.PanedComponent):
    title = _("Saved Searches")
    name = 'savedsearch'
    key = '9'

    duplicate_test_columns = ['Title', 'Date']
    sortable = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.db = SearchDatabase(self.name)

        self.actions.add_action(resource.Action('savedsearch-new', self.action_search_new_cb))
        self.actions.add_action(resource.Action('savedsearch-edit', self.action_search_edit_cb))
        self.actions.add_action(resource.Action('savedsearch-delete', self.action_search_delete_cb))

        self.left_store = Gtk.ListStore()
        self.left_store.set_column_types([str])
        self.left_treeview.set_model(self.left_store)
        self.left_treeview.append_column(Gtk.TreeViewColumn(None, Gtk.CellRendererPixbuf(icon_name='folder-saved-search-symbolic')))
        self.left_treeview.append_column(Gtk.TreeViewColumn(_("Saved search name"), Gtk.CellRendererText(), text=0))
        self.left_treeview.connect('row-activated', self.left_treeview_row_activated_cb)

        self.current_search = None
        self.setup_searches()

    @ampd.task
    async def client_connected_cb(self, client):
        while True:
            self.current_search = None
            self.set_search()
            await self.ampd.idle(ampd.DATABASE)

    def left_treeview_selection_changed_cb(self, left_treeview):
        self.set_search()
        # try:
        #     self.set_search()
        # except:
        #     pass

    def setup_searches(self, target_search=None):
        search_names = list(self.db.get_search_names())
        self.left_store_set_rows(search_names)
        # self.left_treeview.get_preferred_height()        # To avoid a warning
        if target_search:
            store, i = self.left_treeview.get_selection().get_selected()
            if target_search == store.get_value(i, 0):
                self.current_search = None
                self.set_search()
            else:
                n = search_names.index(target_search)
                self.left_treeview.set_cursor(Gtk.TreePath.new_from_indices([n]))

    def action_search_new_cb(self, *args):
        value = self.unit.ssde_struct.edit(self.win, size=self.config[self.unit.unit_config.CONFIG_EDIT_DIALOG_SIZE], scrolled=True)
        if value:
            self.db.add_search(value)
            self.setup_searches(value['name'])

    def action_search_edit_cb(self, *args):
        path, column = self.left_treeview.get_cursor()
        if path:
            self.edit_search(path)

    def edit_search(self, p):
        name = self.left_store.get_value(self.left_store.get_iter(p), 0)
        value = self.db.get_search(name)
        new_value = self.unit.ssde_struct.edit(self.win, value, size=self.config[self.unit.unit_config.CONFIG_EDIT_DIALOG_SIZE], scrolled=True)
        if new_value:
            self.db.delete_search(name)
            self.db.add_search(new_value)
            self.current_search = None
            self.setup_searches(new_value['name'])

    def action_search_delete_cb(self, *args):
        path, column = self.left_treeview.get_cursor()
        if not path:
            return
        name = self.left_store.get_value(self.left_store.get_iter(path), 0)

        dialog = Gtk.Dialog(parent=self.win, title=_("Delete search"))
        dialog.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("_OK"), Gtk.ResponseType.OK)
        dialog.get_content_area().add(Gtk.Label(label=_("Delete search '{}'?").format(name), visible=True))
        reply = dialog.run()
        dialog.destroy()
        if reply == Gtk.ResponseType.OK:
            self.db.delete_search(name)
            self.setup_searches()
            self.set_search()

    def left_treeview_row_activated_cb(self, left_treeview, p, col):
        self.edit_search(p)

    @ampd.task
    async def set_search(self):
        store, i = self.left_treeview.get_selection().get_selected()
        if not i:
            self.set_records([])
            return
        name = self.left_store.get_value(i, 0)
        if name == self.current_search:
            return
        self.current_search = name
        search = self.db.get_search(name)

        songs = []
        for criterion in search['search']:
            songs += await (self.ampd.find if criterion[0] else self.ampd.search)(*sum(criterion[1], []))
        self.records_set_fields(songs)
        sort = search['sort']
        for key, reverse in reversed(sort):
            songs.sort(key=lambda song: song.get(key, ''), reverse=reverse)
        sep = search['separator']
        for i in reversed(range(len(songs) - 1)):
            for j in reversed(range(sep)):
                if songs[i][sort[j][0]] != songs[i + 1][sort[j][0]]:
                    songs[i + 1:i + 1] = (sep - j) * [self.unit.unit_server.separator_song]
                    break
        self.set_records(songs, False)

    def action_reset_cb(self, action, parameter):
        super().action_reset_cb(action, parameter)
        self.current_search = None
        self.set_search()


class SearchDatabase(db.Database):
    def setup_database(self):
        self.connection.cursor().execute('CREATE TABLE IF NOT EXISTS searches(name TEXT PRIMARY KEY, search TEXT, sort TEXT, separator INTEGER)')

    def get_search_names(self):
        return (name for (name,) in self.connection.cursor().execute('SELECT name FROM searches'))

    def get_search(self, name):
        t = self.connection.cursor().execute('SELECT search, sort, separator FROM searches WHERE name=?', (name,)).fetchone()
        return {'name': name, 'search': ast.literal_eval(t[0]), 'sort': ast.literal_eval(t[1]), 'separator': t[2]}

    def add_search(self, search):
        with self.connection:
            search['search'] = repr(search['search'])
            search['sort'] = repr(search['sort'])
            self.connection.cursor().execute('INSERT OR IGNORE INTO searches(name) VALUES(:name)', search)
            self.connection.cursor().execute('UPDATE searches SET search=:search,sort=:sort,separator=:separator WHERE name=:name', search)

    def delete_search(self, name):
        self.connection.cursor().execute('DELETE FROM searches WHERE name=?', (name,))


class __unit__(songlist.UnitWithPanedSongList):
    MODULE_CLASS = SavedSearch

    def __init__(self, name, manager):
        super().__init__(name, manager)

        self.config.access(self.unit_config.CONFIG_EDIT_DIALOG_SIZE, [500, 500])
        new_name = _("<New saved search name>")
        self.ssde_struct = ssde.Dict(
            label=_("Saved search"),
            substructs=[
                ssde.Text(label=_("Saved search name"), name='name', default=new_name, validator=lambda x: x != new_name),
                ssde.List(
                    label=_("Search for one of the following"), name='search',
                    substruct=ssde.TupleAndList(
                        label=_("Search for all of the following"),
                        substructs=[
                            ssde.Boolean(label=_("Exact search")),
                            ssde.Tuple(
                                label=_("Search criterion"),
                                substructs=[
                                    ssde.Choice(label=_("Field"), choices=self.unit_songlist.fields.basic_names),
                                    ssde.Text(label=_("Value"), validator=lambda x: x),
                                ])])),
                ssde.List(
                    label=_("Sort by"), name='sort',
                    substruct=ssde.Tuple(
                        substructs=[
                            ssde.Choice(label=_("Field"), choices=self.unit_songlist.fields.names),
                            ssde.Boolean(label=_("Reversed"))
                        ])),
                ssde.Integer(label=_("Separator depth"), name='separator'),
            ])

        self.new_resource_provider(SavedSearch.name + '.left-context.user-action').add_resources(
            resource.UserAction('mod.savedsearch-new', _("New search"), 'edit'),
            resource.UserAction('mod.savedsearch-edit', _("Edit search"), 'edit'),
            resource.UserAction('mod.savedsearch-delete', _("Delete search"), 'edit'),
        )
