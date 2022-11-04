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


from gi.repository import Gtk

import asyncio


class AsyncDialog(Gtk.Dialog):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.future = None
        self.connect('response', self.response_cb)

    @staticmethod
    def response_cb(self, response_id):
        if self.future is not None and not self.future.done():
            self.future.set_result(response_id)
            self.future = None

    async def run_async(self, *, destroy=False):
        self.set_modal(True)
        self.show()
        if self.future:
            self.future.cancel()
        self.future = asyncio.Future()
        result = await self.future
        if destroy:
            self.destroy()
        return result


class AsyncMessageDialog(AsyncDialog):
    def __init__(self, *, message, cancel_button=True, title=None, **kwargs):
        super().__init__(title=title or message, **kwargs)
        self.get_content_area().add(Gtk.Label(label=message, visible=True))
        if cancel_button:
            self.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
        self.add_button(_("_OK"), Gtk.ResponseType.OK)

    async def run_async(self, **kwargs):
        return await super().run_async(**kwargs) == Gtk.ResponseType.OK


class AsyncTextDialog(AsyncDialog):
    def __init__(self, text=None, **kwargs):
        super().__init__(**kwargs)

        self.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
        self.ok_button = self.add_button(_("_OK"), Gtk.ResponseType.OK)

        self.entry = Gtk.Entry(visible=True)
        self.get_content_area().add(self.entry)
        if text is not None:
            self.entry.set_text(text)
        self.entry.connect('notify::text', self.entry_notify_text_cb)

    async def run_async(self, destroy=False):
        result = await super().run_async()
        result = self.entry.get_text() if result == Gtk.ResponseType.OK else None
        if destroy:
            self.destroy()
        return result

    def entry_notify_text_cb(self, entry, param):
        self.ok_button.set_sensitive(self.validate_text(entry.get_text()))

    @staticmethod
    def validate_text(text):
        return True
