"""Graphical Asynchronous Music Player Client."""

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

import gasyncio.gtk4


class MessageDialogBase(gasyncio.gtk4.Dialog):
    def __init__(self, *, message, title=None, **kwargs):
        if title is None:
            super().__init__(title=message, **kwargs)
        else:
            super().__init__(title=title, widget=Gtk.Label(label=message), **kwargs)


class MessageDialog(MessageDialogBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_button(_("_Close"))


class DialogWithButtons(gasyncio.gtk4.Dialog):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ok_button = self.add_button(_("_OK"), True)
        self.add_button(_("_Cancel"), False)


class QuestionDialog(DialogWithButtons, MessageDialogBase):
    pass


class TextDialog(DialogWithButtons):
    def __init__(self, text=None, **kwargs):
        self.entry = Gtk.Entry()
        if text is not None:
            self.entry.set_text(text)

        super().__init__(widget=self.entry, **kwargs)

        self.entry.connect('notify::text', self.entry_notify_text_cb)
        self.entry_notify_text_cb()

    async def run(self):
        result = await super().run()
        self.entry.disconnect_by_func(self.entry_notify_text_cb)
        return self.entry.get_text() if result else None

    def entry_notify_text_cb(self, *args):
        self.ok_button.set_sensitive(self.validate_text(self.entry.get_text()))

    @staticmethod
    def validate_text(text):
        return True


class SpinButtonDialog(DialogWithButtons):
    def __init__(self, value=None, min_value=0, max_value=0, step_increment=1, page_increment=10, **kwargs):
        self.spin_button = Gtk.SpinButton()
        self.spin_button.set_range(min_value, max_value)
        self.spin_button.set_increments(step_increment, page_increment)
        if value is not None:
            self.spin_button.set_value(value)

        super().__init__(widget=self.spin_button, **kwargs)

    async def run(self):
        return self.spin_button.get_value() if await super().run() else None
