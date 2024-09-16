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


class AIOQueue:
    def __init__(self):
        self.task = None

    def queue_task(self, func, *args, sync=False, **kwargs):
        wrapper = self.wrapper_sync if sync else self.wrapper_async
        self.task = asyncio.create_task(wrapper(self.task, func, *args, **kwargs))
        self.task.add_done_callback(self.task_done)

    @staticmethod
    async def wrapper_async(task, coro, *args, **kwargs):
        await coro(task, *args, **kwargs)
        if task is not None:
            await task

    @staticmethod
    async def wrapper_sync(task, func, *args, **kwargs):
        if task is not None:
            await task
        func(*args, **kwargs)

    def task_done(self, task):
        if task == self.task:
            self.task = None
