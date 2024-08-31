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
    def get_fields(self):
        return self.unit.unit_fields.fields

    def set_songs(self, songs):
        for song in songs:
            self.unit.unit_fields.fields.set_derived_fields(song)
            self.unit.unit_database.cache[song['file']] = song
        self.view.set_values(songs)


class SongListTotalsMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect_clean(self.view.item_store, 'items-changed', self.set_totals)

    def set_totals(self, store, *args):
        time = sum(int(item.get_field('Time', '0')) for item in store)
        self.status = '{} / {}'.format(store.get_n_items(), misc.format_time(time))
