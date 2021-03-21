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


from gi.repository import Gtk

import asyncio


class AsyncDialog(Gtk.Dialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.future = None
        self.connect('response', self.response_cb)

    @staticmethod
    def response_cb(self, response_id):
        if self.future is not None and not self.future.done():
            self.future.set_result(response_id)
            self.future = None

    async def run_async(self):
        self.set_modal(True)
        self.show()
        if self.future:
            self.future.cancel()
        self.future = asyncio.Future()
        return await self.future
