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


from gi.repository import GObject
from gi.repository import Gtk

import logging

from ..util import unit
from ..components import component


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


class Log(component.Component):
    def __init__(self, unit):
        super().__init__(unit)
        self.label = Gtk.Label(selectable=True, visible=True, vexpand=True, halign=Gtk.Align.START, valign=Gtk.Align.START)
        self.widget = self.scrolled_label = Gtk.ScrolledWindow(visible=True)
        self.scrolled_label.add(self.label)

        handler = unit.handler
        self.signal_handler_connect(handler, 'notify::log', self.handler_notify_log_cb)
        self.scrolled_label.get_vadjustment().connect('changed', self.adjustment_changed_cb)
        self.handler_notify_log_cb(handler, None)

    def handler_notify_log_cb(self, handler, param):
        self.label.set_text('\n'.join(handler.format(record) for record in handler.log))

    def adjustment_changed_cb(self, adjustment):
        adjustment.set_value(adjustment.get_upper())


class __unit__(component.UnitMixinComponent, unit.Unit):
    title = _("View log")
    key = '8'

    COMPONENT_CLASS = Log

    def __init__(self, name, manager):
        super().__init__(name, manager)
        self.handler = Handler()
        self.handler.setFormatter(logging.Formatter(fmt='%(asctime)s %(levelname)s: %(name)s: %(message)s (%(pathname)s %(lineno)d)'))
        logging.getLogger().addHandler(self.handler)

    def shutdown(self):
        logging.getLogger().removeHandler(self.handler)
        super().shutdown()
