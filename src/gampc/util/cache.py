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


import asyncio


class AsyncCache:
    def __init__(self, retrieve):
        self.retrieve = retrieve
        self._cache = {}
        self._pending = {}

        self.keys = self._cache.keys
        self.items = self._cache.items
        self.clear = self._cache.clear
        self.remove = self._cache.pop

    def clear(self):
        for task in self._pending.values():
            task.cancel()
        self._cache.clear()
        self._pending.clear()

    async def get(self, key):
        if key in self._cache:
            print(f'E {key}', self._cache[key])
            return self._cache[key]

        if key in self._pending:
            print(f'P {key}')
            value = await self._pending[key]
        else:
            print(f'R {key}')
            task = asyncio.create_task(self.retrieve(key))
            self._pending[key] = task
            value = await task
            del self._pending[key]
            self._cache[key] = value
        return value

    def call(self, cb, key, *args, **kwargs):
        if key in self._cache:
            cb(self._cache[key], *args, **kwargs)
        else:
            asyncio.create_task(self._call(cb, key, *args, **kwargs))

    async def _call(self, cb, key, *args, **kwargs):
        cb(await self.get(key), *args, **kwargs)
