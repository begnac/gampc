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


from gi.repository import Gtk

import asyncio


class DialogAsync(Gtk.Window):
    def __init__(self, **kwargs):
        super().__init__(modal=True, destroy_with_parent=True, **kwargs)
        self.future = asyncio.Future()

        self.button_box = Gtk.Box(halign=Gtk.Align.CENTER)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.main_box.append(self.button_box)

        self.set_child(self.main_box)

        self.connect('close-request', self.button_clicked_cb, self.future, Gtk.ResponseType.CANCEL)

    def add_button(self, label, response):
        button = Gtk.Button.new_with_mnemonic(label)
        button.connect('clicked', self.button_clicked_cb, self.future, response)
        self.button_box.append(button)
        return button

    @staticmethod
    def button_clicked_cb(button, future, response):
        future.set_result(response)

    async def run(self):
        if self.future.done():
            raise RuntimeError
        self.present()
        result = await self.future
        self.destroy()
        return result


class MessageDialogAsync(DialogAsync):
    def __init__(self, *, message, cancel_button=True, title=None, **kwargs):
        super().__init__(title=title or message, **kwargs)
        self.main_box.prepend(Gtk.Label(label=message))
        if cancel_button:
            self.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
        self.add_button(_("_OK"), Gtk.ResponseType.OK)

    async def run(self, **kwargs):
        return await super().run(**kwargs) == Gtk.ResponseType.OK


class TextDialogAsync(DialogAsync):
    def __init__(self, text=None, **kwargs):
        super().__init__(**kwargs)

        self.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
        self.ok_button = self.add_button(_("_OK"), Gtk.ResponseType.OK)

        self.entry = Gtk.Entry()
        self.main_box.prepend(self.entry)
        if text is not None:
            self.entry.set_text(text)
        self.entry.connect('notify::text', self.entry_notify_text_cb)

    async def run(self):
        result = await super().run()
        result = self.entry.get_text() if result == Gtk.ResponseType.OK else None
        self.entry.disconnect_by_func(self.entry_notify_text_cb)
        return result

    def entry_notify_text_cb(self, entry, param):
        self.ok_button.set_sensitive(self.validate_text(entry.get_text()))

    @staticmethod
    def validate_text(text):
        return True
