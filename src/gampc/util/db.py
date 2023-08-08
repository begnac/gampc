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


import xdg.BaseDirectory
import os
import apsw

from .. import __application__


class Cursor(object):
    def __init__(self, cursor, connection):
        self._cursor = cursor
        self._connection = connection

    def execute(self, *args, **kwargs):
        try:
            return self._cursor.execute(*args, **kwargs)
        except apsw.ReadOnlyError:
            self._connection._set_connection()
            raise

    def executemany(self, *args, **kwargs):
        try:
            return self._cursor.executemany(*args, **kwargs)
        except apsw.ReadOnlyError:
            self._connection._set_connection()
            raise


class Connection(object):
    def __init__(self, *args, **kwargs):
        self._init_args = args
        self._init_kwargs = kwargs
        self._set_connection()

    def _set_connection(self):
        self._connection = apsw.Connection(*self._init_args, **self._init_kwargs)

    def cursor(self):
        return Cursor(self._connection.cursor(), self)

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def __enter__(self):
        return self._connection.__enter__()

    def __exit__(self, *args):
        return self._connection.__exit__(*args)


class Database(object):
    def __init__(self, name, *, cache=False):
        super().__init__()
        self.name = name
        self.cache = cache
        self.get_connection()
        self.setup_database()

    def get_connection(self):
        base_path = xdg.BaseDirectory.save_cache_path(__application__) if self.cache else xdg.BaseDirectory.save_data_path(__application__)
        self.connection = Connection(os.path.join(base_path, self.name + '.sqlite'))
        self.connection.cursor().execute('PRAGMA foreign_keys=ON')

    def setup_table(self, table, definition, columns=[]):
        cursor = self.connection.cursor()
        cursor.execute(f'CREATE TABLE IF NOT EXISTS {table}({definition})')
        for column in columns:
            try:
                cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column}')
            except apsw.SQLError:
                pass

    @staticmethod
    def _tuple_to_dict(t, names):
        return {name: t[i] for i, name in enumerate(names) if t[i] is not None}
