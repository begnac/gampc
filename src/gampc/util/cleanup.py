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

from .logger import logger


class CleanupBaseMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cleanup_below = []

    def __del__(self):
        logger.debug(f"Deleting {self}")

    def add_cleanup_below(self, *belows):
        for below in belows:
            self._cleanup_below.append(below)

    def cleanup(self):
        for below in self._cleanup_below:
            below.cleanup()
        logger.debug(f"Cleaned up {self}")


class CleanupSignalMixin(CleanupBaseMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cleanup_signal = []

    def cleanup(self):
        for target, handler in self._cleanup_signal:
            target.disconnect(handler)
        del self._cleanup_signal
        super().cleanup()

    def connect_clean(self, target, *args):
        handler = target.connect(*args)
        self._cleanup_signal.append((target, handler))


class CleanupCssMixin(CleanupBaseMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def cleanup(self):
        Gtk.StyleContext.remove_provider_for_display(Gdk.Display.get_default(), self.css_provider)
        super().cleanup()
