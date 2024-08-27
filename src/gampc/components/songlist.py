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

from ..util import misc

from . import itemlist


class SongList(itemlist.ItemList):
    # use_resources = ['itemlist', 'songlist']
    DND_TARGET = 'GAMPC_SONG'

    def __init__(self, unit, *args, **kwargs):
        self.cache = unit.unit_database.cache
        self.fields = unit.unit_songlist.fields
        super().__init__(unit, *args, **kwargs)
        # self.songlist_actions = self.add_actions_provider('songlist')

    def set_songs(self, songs):
        for song in songs:
            self.unit.unit_songlist.fields.set_derived_fields(song)
            self.cache[song['file']] = song
        self.set_values(songs)

    # def get_filenames(self, selection):
    #     return self.view.get_filenames(selection)

    # def records_set_fields(self, songs):
    #     for song in songs:
    #         gfile = Gio.File.new_for_path(GLib.build_filenamev([self.unit.unit_songlist.config.music_dir._get(), song['file']]))
    #         if gfile.query_exists():
    #             song['_gfile'] = gfile
    #         else:
    #             song['_status'] = self.RECORD_MODIFIED
    #     super().records_set_fields(songs)


class SongListTotalsMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.signal_handler_connect(self.view.item_store, 'items-changed', self.set_totals)

    def set_totals(self, store, *args):
        time = sum(int(item.get_field('Time', '0')) for item in store)
        self.status = '{} / {}'.format(store.get_n_items(), misc.format_time(time))
