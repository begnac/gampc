# coding: utf-8
#
# Graphical Asynchronous Music Player Client
#
# Copyright (C) 2021 Itaï BEN YAACOV
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


class Unit(GObject.Object):
    REQUIRED_UNITS = []

    def __init__(self, name, manager):
        super().__init__()
        self.name = name
        self.manager = manager
        self.providers = []
        for required in self.REQUIRED_UNITS:
            setattr(self, 'unit_' + required, manager._use_unit(required))

    def shutdown(self):
        logger.debug("Shutting down unit {self}".format(self=self))
        for required in reversed(self.REQUIRED_UNITS):
            self.manager._free_unit(required)
        del self.providers
        del self.manager

    def new_resource_provider(self, name):
        provider = resource.ResourceProvider(name)
        self.providers.append(provider)
        return provider

    def link_providers(self, aggregator):
        for provider in self.providers:
            if provider.name in [aggregator.name] + aggregator.also_wants:
                aggregator.link(provider)

    def unlink_providers(self, aggregator):
        for provider in reversed(self.providers):
            if provider.name in [aggregator.name] + aggregator.also_wants:
                aggregator.unlink(provider)

    def __del__(self):
        logger.debug("Deleting {self}".format(self=self))


class UnitWithCss(Unit):
    def __init__(self, name, manager):
        super().__init__(name, manager)
        self.css_provider = Gtk.CssProvider.new()
        self.css_provider.load_from_data(self.CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def shutdown(self):
        Gtk.StyleContext.remove_provider_for_screen(Gdk.Screen.get_default(), self.css_provider)
        super().shutdown()


class UnitWithConfig(Unit):
    def __init__(self, name, manager):
        self.REQUIRED_UNITS = ['config'] + self.REQUIRED_UNITS
        super().__init__(name, manager)
        self.config = self.unit_config.config.subtree(name)


class UnitWithServer(Unit):
    def __init__(self, name, manager):
        self.REQUIRED_UNITS = ['server'] + self.REQUIRED_UNITS
        super().__init__(name, manager)
        self.ampd = self.unit_server.ampd_client.executor.sub_executor()

    def shutdown(self):
        self.ampd.close()
        super().shutdown()


class UnitManager(GObject.Object):
    def __init__(self):
        GObject.Object.__init__(self)
        self._target = []
        self._units = collections.OrderedDict()
        self._aggregators = []

    def set_target(self, *target):
        for name in target:
            self._use_unit(name)
        for name in reversed(self._target):
            self._free_unit(name)
        self._target = target

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
                unit.link_providers(aggregator)
        unit.use_count += 1
        return unit

    def _free_unit(self, name):
        if name not in self._units:
            raise RuntimeError
        unit = self._units[name]
        unit.use_count -= 1
        if unit.use_count == 0:
            for aggregator in reversed(self._aggregators):
                unit.unlink_providers(aggregator)
            del self._units[name]
            unit.shutdown()

    def add_aggregator(self, aggregator):
        for unit in self._units.values():
            unit.link_providers(aggregator)
        self._aggregators.append(aggregator)

    def remove_aggregator(self, aggregator):
        self._aggregators.remove(aggregator)
        for unit in reversed(self._units.values()):
            unit.unlink_providers(aggregator)

    def create_aggregator(self, name, resource_added_cb, resource_removed_cb, *cb_params, also_wants=[]):
        aggregator = resource.ResourceAggregator(name, also_wants)
        aggregator.connect('resource-added', resource_added_cb, *cb_params)
        aggregator.connect('resource-removed', resource_removed_cb, *cb_params)
        self.add_aggregator(aggregator)
        return aggregator

    def __del__(self):
        logger.debug("Deleting {self}".format(self=self))
