# coding: utf-8
#
# Graphical Asynchronous Music Player Client
#
# Copyright (C) 2015-2022 Itaï BEN YAACOV
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


import datetime

import ampd

from ..util import unit
from ..util import db


LAST_QUERY = '_CACHE_Last_Query'
LAST_MODIFIED = 'Last_Modified'


class CacheDatabase(db.Database):
    def __init__(self, name, keyfield, fields):
        self.fields = fields
        self.keyfield = keyfield
        super().__init__(name, cache=True)

    def setup_database(self):
        self.setup_table('cache', f'{self.keyfield} TEXT NOT NULL PRIMARY KEY', self.fields + [LAST_QUERY])
        cursor = self.connection.cursor()
        cursor.execute(f'CREATE TABLE IF NOT EXISTS {LAST_MODIFIED}({LAST_MODIFIED})')
        if not list(self.connection.cursor().execute(f'SELECT {LAST_MODIFIED} FROM {LAST_MODIFIED}')):
            cursor.execute(f'INSERT INTO {LAST_MODIFIED} VALUES(NULL)')

    def query(self, *keys):
        reply = {}
        with self.connection:
            fields = ','.join(self.fields)
            keyvalues = ','.join(['?'] * len(keys))
            self.connection.cursor().execute(f'UPDATE cache SET {LAST_QUERY}=? WHERE {self.keyfield} IN ({keyvalues})', [self.now()] + list(keys))
            result = self.connection.cursor().execute(f'SELECT {fields} FROM cache WHERE {self.keyfield} IN ({keyvalues})', keys)
            for line in result:
                value = self._tuple_to_dict(line, self.fields)
                reply[value[self.keyfield]] = value
            return reply

    def add_record(self, record):
        self.connection.cursor().execute('INSERT INTO cache({fields}) VALUES({values})'.format(fields=','.join(self.fields + [LAST_QUERY]), values=','.join(['?'] * (len(self.fields) + 1))), [record.get(name) for name in self.fields] + [self.now()])

    @staticmethod
    def now():
        return datetime.datetime.now(tz=datetime.timezone.utc).isoformat(timespec='seconds')

    def get_last_last_modified(self):
        for line in self.connection.cursor().execute(f'SELECT MAX({LAST_MODIFIED}) FROM cache'):
            return line[0]

    def get_checked_last_modified(self):
        for line in self.connection.cursor().execute(f'SELECT {LAST_MODIFIED} FROM {LAST_MODIFIED}'):
            return line[0]

    def update_with(self, songs):
        if not songs:
            return
        last_modified = max(song[LAST_MODIFIED] for song in songs)
        cursor = self.connection.cursor()
        with self.connection:
            for song in songs:
                set_values = ','.join(f'{field}=:{field}' for field in self.fields)
                cursor.execute(f'UPDATE cache SET {set_values} WHERE file=:file', song)
            cursor.execute(f'UPDATE {LAST_MODIFIED} SET {LAST_MODIFIED}=?', (last_modified,))


class __unit__(unit.UnitMixinServer, unit.Unit):
    def __init__(self, name, manager):
        self.REQUIRED_UNITS = ['songlist'] + self.REQUIRED_UNITS
        super().__init__(name, manager)

        self.fields = manager.get_unit('songlist').fields.basic_names
        self.db = CacheDatabase(name, 'file', self.fields)

    @ampd.task
    async def client_connected_cb(self, client):
        while True:
            await self.update_cache()
            await self.ampd.idle(ampd.DATABASE)

    async def get_songs(self, *filenames):
        songs = self.db.query(*filenames)
        for filename in filenames:
            if filename not in songs:
                song = await self.ampd.find(f'(file == "{filename}")')
                if song:
                    self.db.add_record(song[0])
                    songs[filename] = song[0]
        return songs

    async def update_cache(self):
        last = self.db.get_checked_last_modified() or self.db.get_last_last_modified()
        if last is not None:
            self.db.update_with(await self.ampd.find(f'(modified-since "{last}")'))
