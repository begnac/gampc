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
from gi.repository import Gdk
from gi.repository import Gtk

import importlib
import collections

from . import resource
from .logger import logger


class UnitLoadError(Exception):
    pass


class Unit(resource.ResourceProvider):
    REQUIRED_UNITS = []

    def __init__(self, name, manager):
        super().__init__()
        self.name = name
        self.manager = manager

        loaded_required = []
        try:
            for required in self.REQUIRED_UNITS:
                setattr(self, 'unit_' + required, manager._use_unit(required))
                loaded_required.append(required)
        except UnitLoadError:
            for required in loaded_required:
                self.manager._free_unit(required)
            raise

    def shutdown(self):
        logger.debug(f"Shutting down unit {self}")
        self.remove_all_resources()
        for required in reversed(self.REQUIRED_UNITS):
            self.manager._free_unit(required)
        del self.manager

    def __del__(self):
        logger.debug("Deleting {self}".format(self=self))


class UnitMixinCss:
    def __init__(self, name, manager):
        super().__init__(name, manager)
        self.css_provider = Gtk.CssProvider()
        self.css_provider.load_from_data(self.CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def shutdown(self):
        Gtk.StyleContext.remove_provider_for_screen(Gdk.Screen.get_default(), self.css_provider)
        super().shutdown()


class UnitMixinConfig:
    def __init__(self, name, manager):
        self.REQUIRED_UNITS = ['config'] + self.REQUIRED_UNITS
        super().__init__(name, manager)
        self.config = self.unit_config.load_config(name)


class UnitMixinServer:
    def __init__(self, name, manager):
        self.REQUIRED_UNITS = ['server'] + self.REQUIRED_UNITS
        super().__init__(name, manager)
        self.ampd = self.unit_server.ampd_client.executor.sub_executor()

        self.unit_server.ampd_client.connect('client-connected', self.client_connected_cb)
        if self.ampd.get_is_connected():
            self.client_connected_cb(self.unit_server.ampd_client)

    def shutdown(self):
        self.unit_server.ampd_client.disconnect_by_func(self.client_connected_cb)
        self.ampd.close()
        super().shutdown()

    @staticmethod
    def client_connected_cb(client):
        pass


class UnitMixinCache:
    def __init__(self, name, manager):
        self.REQUIRED_UNITS = ['cache'] + self.REQUIRED_UNITS
        super().__init__(name, manager)
        self.cache = manager.get_unit('cache')


class UnitManager(GObject.Object):
    def __init__(self):
        GObject.Object.__init__(self)
        self._target = []
        self._units = collections.OrderedDict()
        self._aggregators = []

    def set_target(self, *target):
        real_target = []
        for name in target:
            try:
                self._use_unit(name)
                real_target.append(name)
            except UnitLoadError:
                pass
        for name in reversed(self._target):
            self._free_unit(name)
        self._target = real_target
        return real_target

    def get_unit(self, name):
        return self._units[name]

    def _use_unit(self, name):
        if name in self._units:
            unit = self._units[name]
        else:
            unit_module = importlib.import_module('gampc.units.' + name)
            unit = self._units[name] = unit_module.__unit__(name, self)
            unit.use_count = 0
            for aggregator in self._aggregators:
                aggregator.link(unit)
        unit.use_count += 1
        return unit

    def _free_unit(self, name):
        if name not in self._units:
            raise RuntimeError
        unit = self._units[name]
        unit.use_count -= 1
        if unit.use_count == 0:
            for aggregator in reversed(self._aggregators):
                aggregator.unlink(unit)
            del self._units[name]
            unit.shutdown()

    def add_aggregator(self, aggregator):
        for unit in self._units.values():
            aggregator.link(unit)
        self._aggregators.append(aggregator)

    def remove_aggregator(self, aggregator):
        self._aggregators.remove(aggregator)
        for unit in reversed(self._units.values()):
            aggregator.unlink(unit)

    def __del__(self):
        logger.debug("Deleting {self}".format(self=self))
