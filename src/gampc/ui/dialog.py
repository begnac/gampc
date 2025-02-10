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


from gi.repository import Gdk
from gi.repository import Gtk

import asyncio


class DialogAsync(Gtk.Window):
    def __init__(self, *, cancel_button=True, **kwargs):
        self.button_box = Gtk.Box(halign=Gtk.Align.CENTER)
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.main_box.append(self.button_box)
        self.future = asyncio.Future()

        super().__init__(modal=True, destroy_with_parent=True, child=self.main_box, **kwargs)

        self.connect('close-request', self.button_clicked_cb, self.future, Gtk.ResponseType.CANCEL)

        self.shortcut = Gtk.ShortcutController()
        self.add_controller(self.shortcut)
        self.shortcut.add_shortcut(Gtk.Shortcut(trigger=Gtk.KeyvalTrigger(keyval=Gdk.KEY_Escape, modifiers=Gdk.ModifierType.NO_MODIFIER_MASK), action=Gtk.CallbackAction.new(self.escape_pressed_cb, self.future)))

        if cancel_button:
            self.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
        self.ok_button = self.add_button(_("_OK"), Gtk.ResponseType.OK)

    def add_button(self, label, response):
        button = Gtk.Button.new_with_mnemonic(label)
        button.connect('clicked', self.button_clicked_cb, self.future, response)
        self.button_box.append(button)
        return button

    @staticmethod
    def button_clicked_cb(button, future, response):
        future.set_result(response)

    @staticmethod
    def escape_pressed_cb(widget, arg, future):
        future.set_result(Gtk.ResponseType.CANCEL)

    async def run(self):
        if self.future.done():
            raise RuntimeError
        self.present()
        result = await self.future
        self.destroy()
        return result == Gtk.ResponseType.OK


class MessageDialogAsync(DialogAsync):
    def __init__(self, *, message, title=None, **kwargs):
        super().__init__(title=title or message, **kwargs)
        self.main_box.prepend(Gtk.Label(label=message))


class TextDialogAsync(DialogAsync):
    def __init__(self, text=None, **kwargs):
        super().__init__(**kwargs)

        self.entry = Gtk.Entry()
        self.main_box.prepend(self.entry)
        if text is not None:
            self.entry.set_text(text)
        self.entry.connect('notify::text', self.entry_notify_text_cb)

    async def run(self):
        result = self.entry.get_text() if await super().run() else None
        self.entry.disconnect_by_func(self.entry_notify_text_cb)
        return result

    def entry_notify_text_cb(self, entry, param):
        self.ok_button.set_sensitive(self.validate_text(entry.get_text()))

    @staticmethod
    def validate_text(text):
        return True


class SpinButtonDialogAsync(DialogAsync):
    def __init__(self, value=None, min_value=0, max_value=0, step_increment=1, page_increment=10, **kwargs):
        super().__init__(**kwargs)

        self.spin_button = Gtk.SpinButton()
        self.spin_button.set_range(min_value, max_value)
        self.spin_button.set_increments(step_increment, page_increment)
        if value is not None:
            self.spin_button.set_value(value)
        self.main_box.prepend(self.spin_button)

    async def run(self):
        return self.spin_button.get_value() if await super().run() else None
