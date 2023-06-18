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


from gi.repository import GLib
from gi.repository import Gtk

import logging


class Handeler(logging.Handler):
    MAX_INFOBARS = 5

    def __init__(self, box, timeout):
        super().__init__(logging.INFO)
        self.box = box
        self.timeout = timeout
        self.infobars = []

    def remove_infobar(self, infobar, response=None):
        self._remove_infobar(infobar)
        GLib.source_remove(infobar.timeout)

    def remove_infobar_timeout(self, infobar):
        self._remove_infobar(infobar)
        return GLib.SOURCE_REMOVE

    def _remove_infobar(self, infobar):
        self.infobars.remove(infobar)
        self.box.remove(infobar)

    def cull_infobars(self, n=0):
        while len(self.infobars) > n:
            self.remove_infobar(self.infobars[0])

    def emit(self, record):
        self.cull_infobars(self.MAX_INFOBARS - 1)

        message_type = Gtk.MessageType.ERROR if record.levelno >= 40 else Gtk.MessageType.WARNING if record.levelno >= 30 else Gtk.MessageType.INFO
        message_icon = 'error' if record.levelno >= 40 else 'warning' if record.levelno >= 30 else 'information'
        infobar = Gtk.InfoBar(visible=True, message_type=message_type, show_close_button=True)
        infobar.get_content_area().add(Gtk.Image(visible=True, icon_name='dialog-' + message_icon, icon_size=Gtk.IconSize.LARGE_TOOLBAR))
        infobar.get_content_area().add(Gtk.Label(visible=True, wrap=True, label=record.msg))
        infobar.connect('response', self.remove_infobar)
        infobar.timeout = GLib.timeout_add(self.timeout, self.remove_infobar_timeout, infobar)
        self.box.add(infobar)
        self.infobars.append(infobar)

    def shutdown(self):
        self.cull_infobars()
