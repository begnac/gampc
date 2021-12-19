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


from gi.repository import GLib
from gi.repository import Gtk

import ampd

from gampc.util import ssde
from gampc.util import resource
from gampc.units import songlist


class PlayQueue(songlist.SongListWithTotals, songlist.SongListWithAdd):
    title = _("Play Queue")
    name = 'playqueue'
    key = '1'

    duplicate_test_columns = ['Title']

    def __init__(self, unit):
        super().__init__(unit)
        self.actions.add_action(resource.Action('playqueue-high-priority', self.action_priority_cb))
        self.actions.add_action(resource.Action('playqueue-normal-priority', self.action_priority_cb))
        self.actions.add_action(resource.Action('playqueue-choose-priority', self.action_priority_cb))
        self.actions.add_action(resource.Action('playqueue-shuffle', self.action_shuffle_cb, dangerous=True, protector=unit.unit_persistent))
        self.actions.add_action(resource.Action('playqueue-go-to-current', self.action_go_to_current_cb))
        self.signal_handler_connect(unit.unit_server.ampd_server_properties, 'notify::current-song', self.notify_current_song_cb)
        for name in self.actions.list_actions():
            if name.startswith('playqueue-ext-'):
                self.actions.remove(name)
        self.signal_handler_connect(self.treeview, 'cursor-changed', self.cursor_changed_cb)
        self.cursor_by_profile = {}
        self.set_cursor = False

    def cursor_changed_cb(self, treeview):
        if not self.set_cursor:
            self.cursor_by_profile[self.unit.unit_server.server_profile] = self.treeview.get_cursor().path

    @ampd.task
    async def client_connected_cb(self, client):
        self.set_cursor = True
        while True:
            self.set_records(await self.ampd.playlistinfo())
            if self.set_cursor:
                self.treeview.set_cursor(self.cursor_by_profile.get(self.unit.unit_server.server_profile) or Gtk.TreePath(), None, False)
                self.set_cursor = False
            await self.ampd.idle(ampd.PLAYLIST)

    def data_func(self, column, renderer, store, i, j):
        super().data_func(column, renderer, store, i, j)
        if self.unit.unit_server.ampd_server_properties.state != 'stop' and store.get_record(i).Id == self.unit.unit_server.ampd_server_properties.current_song.get('Id'):
            renderer.set_property('font', 'italic bold')
            bg = self._mix_colors(1, 1, 1)
            renderer.set_property('background-rgba', bg)
        else:
            renderer.set_property('font', None)
        if column.field.name == 'FormattedTime' and store.get_record(i).Prio is not None:
            bg = self._mix_colors(0, int(store.get_record(i).Prio) / 255.0, 0)
            renderer.set_property('background-rgba', bg)

    @ampd.task
    async def action_priority_cb(self, action, parameter):
        songs, refs = self.treeview.get_selection_rows()
        if not songs:
            return

        if '-choose-' in action.get_name():
            priority = sum(int(song.get('Prio', 0)) for song in songs) // len(songs)
            struct = ssde.Integer(default=priority, min_value=0, max_value=255)
            priority = await struct.edit_async(self.win)
            if priority is None:
                return
        else:
            priority = 255 if '-high-' in action.get_name() else 0
        if songs:
            await self.ampd.prioid(priority, *(song['Id'] for song in songs))

    @ampd.task
    async def action_shuffle_cb(self, action, parameter):
        await self.ampd.shuffle()

    def action_go_to_current_cb(self, action, parameter):
        if self.unit.unit_server.ampd_server_properties.current_song:
            p = Gtk.TreePath.new_from_string(self.unit.unit_server.ampd_server_properties.current_song['Pos'])
            self.treeview.set_cursor(p)
            self.treeview.scroll_to_cell(p, None, True, 0.5, 0.0)

    def notify_current_song_cb(self, *args):
        self.treeview.queue_draw()

    def record_new_cb(self, store, i):
        ampd.task(self.ampd.addid)(store.get_record(i).file, store.get_path(i).get_indices()[0])

    def record_delete_cb(self, store, i):
        song_id = store.get_record(i).Id
        m = int(store.get_string_from_iter(i))
        for n in range(store.iter_n_children()):
            if n != m and store.get_record(store.iter_nth_child(None, n)).Id == song_id:
                ampd.task(self.ampd.command_list)((self.ampd.swap(n, m), self.ampd.delete(m)))
                store.remove(i)
                return
        if not (self.unit.unit_persistent.protected and self.unit.unit_server.ampd_server_properties.state == 'play' and self.unit.unit_server.ampd_server_properties.current_song.get('pos') == song_id):
            ampd.task(self.ampd.deleteid)(song_id)
            store.remove(i)

    @ampd.task
    async def treeview_row_activated_cb(self, treeview, p, column):
        if not self.unit.unit_persistent.protected:
            await self.ampd.playid(self.store.get_record(self.store.get_iter(p)).Id)


@ampd.task
async def action_playqueue_add_replace_cb(songlist_, action, parameter):
    filenames = songlist_.get_filenames(parameter.get_boolean())
    replace = '-replace' in action.get_name()
    if replace:
        await songlist_.ampd.clear()
    await songlist_.ampd.command_list(songlist_.ampd.add(filename) for filename in filenames)
    if replace:
        await songlist_.ampd.play()


@ampd.task
async def action_playqueue_add_high_priority_cb(songlist_, action, parameter):
    filenames = songlist_.get_filenames(parameter.get_boolean())
    queue = {song['file']: song for song in await songlist_.ampd.playlistinfo()}
    Ids = []
    for filename in filenames:
        Ids.append(queue[filename]['Id'] if filename in queue else await songlist_.ampd.addid(filename))
    await songlist_.ampd.prioid(255, *Ids)


class __unit__(songlist.UnitWithSongList):
    MODULE_CLASS = PlayQueue

    def __init__(self, name, manager):
        super().__init__(name, manager)

        self.new_resource_provider('app.user-action').add_resources(
            resource.UserAction('mod.playqueue-shuffle', _("Shuffle"), 'edit/component'),
            resource.UserAction('mod.playqueue-go-to-current', _("Go to current song"), 'edit/component', ['<Control>z'])
        )

        self.new_resource_provider('songlist.action').add_resources(
            resource.ActionModel('playqueue-ext-add-high-priority', action_playqueue_add_high_priority_cb,
                                 dangerous=True, parameter_type=GLib.VariantType.new('b')),
            *(resource.ActionModel('playqueue-ext' + verb, action_playqueue_add_replace_cb,
                                   dangerous=(verb == '-replace'), parameter_type=GLib.VariantType.new('b'))
              for verb in ('-add', '-replace')),
        )

        for name, parameter in (('context', '(true)'), ('left-context', '(false)')):
            self.new_resource_provider('songlist.{name}.user-action'.format(name=name)).add_resources(
                resource.UserAction('mod.playqueue-ext-add' + parameter, _("Add to play queue"), 'action'),
                resource.UserAction('mod.playqueue-ext-replace' + parameter, _("Replace play queue"), 'action'),
                resource.UserAction('mod.playqueue-ext-add-high-priority' + parameter, _("Add to play queue with high priority"), 'action'),
            )

        self.new_resource_provider(PlayQueue.name + '.context.menu').add_resources(
            resource.MenuPath('other/playqueue-priority', _("Priority for random mode"), is_submenu=True),
        )

        self.new_resource_provider(PlayQueue.name + '.context.user-action').add_resources(
            resource.UserAction('mod.playqueue-high-priority', _("High"), 'other/playqueue-priority'),
            resource.UserAction('mod.playqueue-normal-priority', _("Normal"), 'other/playqueue-priority'),
            resource.UserAction('mod.playqueue-choose-priority', _("Choose"), 'other/playqueue-priority'),
            resource.UserAction('mod.playqueue-shuffle', _("Shuffle"), 'other'),
        )
