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

import importlib
import collections

from . import cleanup
from .logger import logger


class UnitLoadError(Exception):
    pass


class Unit(cleanup.CleanupSignalMixin, GObject.Object):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.name = self.__module__.rsplit('.', 1)[1]

        self.loaded_required = []

    def cleanup(self):
        while self.loaded_required:
            self.manager._free_unit(self.loaded_required.pop())
        del self.manager
        super().cleanup()

    def require(self, name):
        unit = self.manager._use_unit(name)
        setattr(self, 'unit_' + name, unit)
        self.loaded_required.append(name)
        return unit


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
            unit_module = importlib.import_module('gampc.unit.' + name)
            unit = self._units[name] = unit_module.__unit__(self)
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
            unit.cleanup()

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
