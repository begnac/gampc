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


from ..util import resource
from ..util import unit


class __unit__(unit.Unit):
    REQUIRED_UNITS = ['menubar']

    def __init__(self, name, manager):
        super().__init__(name, manager)
        self._component_factories = {}
        self._components = {}

        self.add_resources(
            'app.menu',
            resource.MenuPath('components/components', _("Press <Ctrl> for a new instance")),
            resource.MenuPath('components/current'),
            resource.MenuAction('components/current', 'app.component-stop', _("Stop component"), ['<Control><Shift>w'])
        )

    def shutdown(self):
        for components in self._components.values():
            for component in components:
                component.shutdown()
        super().shutdown()

    def register_component_factory(self, name, factory):
        if name in self._component_factories:
            raise RuntimeError
        self._component_factories[name] = factory

    def unregister_component_factory(self, name):
        del self._component_factories[name]

    def get_component(self, name, new_instance):
        if not self._components.setdefault(name, []) or new_instance:
            component = self._component_factories[name]()
        else:
            component = self._components[name].pop(0)
        self._components[name].append(component)
        return component

    def get_free_component(self):
        for components in self._components.values():
            for component in components:
                if not component.win:
                    return component

    def remove_component(self, component):
        component.shutdown()
        for name in self._components:
            if component in self._components[name]:
                self._components[name].remove(component)
                if not self._components[name]:
                    del self._components[name]
                return
        raise RuntimeError
