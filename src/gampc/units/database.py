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
    def __init__(self, name, manager):
        super().__init__(name, manager)
        self.require('songlist')
        self.cache = util.cache.AsyncCache(self.database_retrieve)

    def shutdown(self):
        super().shutdown()
        del self.cache

    @ampd.task
    async def client_connected_cb(self, client):
        while True:
            await self.ampd.idle(ampd.DATABASE)
            self.cache.clear()

    async def database_retrieve(self, key):
        try:
            songs = await self.ampd.find('file', key)
        except Exception as e:
            print(key, e)
            return {}
        if len(songs) == 0:
            song = {'file': key}
        elif len(songs) == 1:
            song = songs[0]
        else:
            raise ValueError
        self.unit_songlist.fields.set_derived_fields(song)
        return song
