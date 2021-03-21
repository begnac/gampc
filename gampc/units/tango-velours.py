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


from gampc.util import unit


def notify_current_song_cb(unit_server, param):
    if unit_server.current_song.get('Name') == 'RadioTango-Velours':
        unit_server.handler_block_by_func(notify_current_song_cb)
        song = unit_server.current_song.copy()
        title = song.get('Title', '')
        if ' - ' in title:
            artist, title = title.split(' - ', 1)
            song['orig-tango-velours'] = unit_server.current_song
            song.update(Artist=artist, Title=title, Performer='Radio Tango Velours')
            unit_server.current_song = song
        unit_server.handler_unblock_by_func(notify_current_song_cb)


class __unit__(unit.UnitWithServer):
    def __init__(self, name, manager):
        super().__init__(name, manager)
        self.unit_server.connect('notify::current-song', notify_current_song_cb)
        notify_current_song_cb(self.unit_server, None)

    def shutdown(self):
        self.unit_server.disconnect_by_func(notify_current_song_cb)
        if 'orig-tango-velours' in self.unit_server.current_song:
            self.unit_server.current_song = self.unit_server.current_song['orig-tango-velours']
        super().shutdown()
