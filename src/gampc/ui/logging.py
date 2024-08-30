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


from gi.repository import GLib
from gi.repository import Gtk

import logging


class Handler(logging.Handler):
    MAX_MESSAGES = 5

    def __init__(self, timeout):
        super().__init__(logging.INFO)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, can_focus=False)
        self.timeout = timeout
        self.messages = []

    def remove_message(self, message, response=None):
        self._remove_message(message)
        GLib.source_remove(message.timeout)

    def remove_message_timeout(self, message):
        self._remove_message(message)
        return GLib.SOURCE_REMOVE

    def _remove_message(self, message):
        self.messages.remove(message)
        self.box.remove(message)

    def cull_messages(self, n=0):
        while len(self.messages) > n:
            self.remove_message(self.messages[0])

    def emit(self, record):
        self.cull_messages(self.MAX_MESSAGES - 1)

        message_type = Gtk.MessageType.ERROR if record.levelno >= 40 else Gtk.MessageType.WARNING if record.levelno >= 30 else Gtk.MessageType.INFO
        message_icon = 'error' if record.levelno >= 40 else 'warning' if record.levelno >= 30 else 'information'
        message = Gtk.InfoBar(message_type=message_type, show_close_button=True)
        message.add_child(Gtk.Image(icon_name='dialog-' + message_icon, icon_size=Gtk.IconSize.LARGE))
        message.add_child(Gtk.Label(wrap=True, label=record.msg))
        message.connect('response', self.remove_message)
        message.timeout = GLib.timeout_add(self.timeout, self.remove_message_timeout, message)
        self.box.append(message)
        self.messages.append(message)

    def cleanup(self):
        self.cull_messages()
