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


from gi.repository import GObject
from gi.repository import Gtk

import logging

from ..util import cleanup
from ..util import unit

from . import mixins


class Handler(logging.Handler, GObject.Object):
    log = GObject.Property()

    def __init__(self):
        logging.Handler.__init__(self)
        GObject.Object.__init__(self)
        self.flush()

    def emit(self, record):
        self.log.append(record)
        self.notify('log')

    def flush(self):
        self.log = []


class LogWidget(cleanup.CleanupSignalMixin, Gtk.ScrolledWindow):
    def __init__(self, handler):
        self.label = Gtk.Label(selectable=True, vexpand=True, halign=Gtk.Align.START, valign=Gtk.Align.END, hexpand=True)
        super().__init__(child=self.label)

        self.connect_clean(handler, 'notify::log', self.handler_notify_log_cb)
        self.connect_clean(self.get_vadjustment(), 'changed', self.adjustment_changed_cb)
        self.handler_notify_log_cb(handler, None)

    def handler_notify_log_cb(self, handler, param):
        self.label.set_text('\n'.join(handler.format(record) for record in handler.log))

    def adjustment_changed_cb(self, adjustment):
        adjustment.set_value(adjustment.get_upper())


class __unit__(mixins.UnitComponentMixin, unit.Unit):
    TITLE = _("View log")
    KEY = '8'

    def __init__(self, manager):
        super().__init__(manager)
        self.handler = Handler()
        self.handler.setFormatter(logging.Formatter(fmt='%(asctime)s %(levelname)s: %(name)s: %(message)s (%(pathname)s %(lineno)d)'))
        logging.getLogger().addHandler(self.handler)

    def cleanup(self):
        logging.getLogger().removeHandler(self.handler)
        super().cleanup()

    def new_widget(self):
        return LogWidget(self.handler)
