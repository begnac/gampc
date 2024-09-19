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


class AsyncCache(dict):
    def __init__(self):
        super().__init__()
        self._pending = {}

    async def ensure_keys(self, keys):
        async with asyncio.TaskGroup() as tasks:
            for key in keys:
                tasks.create_task(self.ensure_key(key))

    async def ensure_key(self, key):
        while key in self._pending:
            await self._pending[key]
        if key not in self:
            self._pending[key] = asyncio.current_task()
            self[key] = await self.retrieve(key)
            del self._pending[key]

    async def get_async(self, key):
        await self.ensure_key(key)
        return self[key]
