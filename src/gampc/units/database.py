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


from .. import util

import ampd


class __unit__(util.unit.UnitServerMixin, util.unit.Unit):
    def __init__(self, *args):
        super().__init__(*args)
        self.require('songlist')
        self.cache = util.cache.AsyncCache(self.cache_retrieve)

    def shutdown(self):
        super().shutdown()
        del self.cache

    @ampd.task
    async def client_connected_cb(self, client):
        while True:
            await self.ampd.idle(ampd.DATABASE)
            self.cache.clear()

    async def cache_retrieve(self, key):
        try:
            songs = await self.ampd.find('file', key)
        except Exception as e:
            print(key, e)
            return {}
        if len(songs) == 0:
            song = {'file': key}
        elif len(songs) == 1:
            song = songs[0]
            self.unit_songlist.fields.set_derived_fields(song)
        else:
            raise ValueError
        return song
