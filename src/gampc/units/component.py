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
        self._component_classes = {}
        self._components = []

        self.menu_provider = self.new_resource_provider('app.menu')
        self.menu_provider.add_resources(
            resource.MenuPath('components/components', _("Press <Ctrl> for a new instance")),
            resource.MenuPath('components/current'),
            resource.UserAction('app.component-stop', _("Stop component"), 'components/current', ['<Control><Shift>w'])
        )

    def shutdown(self):
        for component in self._components:
            component.destroy()
        del self._components
        super().shutdown()

    def register_component_class(self, component_class, *args, **kwargs):
        name = component_class.name
        if name in self._component_classes:
            raise RuntimeError
        user_action = resource.UserAction('app.component-start("{name}")'.format(name=name),
                                          component_class.title, 'components/components', ['<Alt>' + component_class.key, '<Control><Alt>' + component_class.key])
        self._component_classes[name] = component_class, args, kwargs, user_action
        self.menu_provider.add_resource(user_action)

    def unregister_component_class(self, component_class):
        name = component_class.name
        *_, user_action = self._component_classes[name]
        self.menu_provider.remove_resource(user_action)
        del self._component_classes[name]

    def get_component(self, name, new_instance):
        component = (not new_instance and self._pop_component(name)) or self._new_component(name)
        self._components.append(component)
        return component

    def _new_component(self, name):
        component_class, args, kwargs, _ = self._component_classes[name]
        return component_class(*args, **kwargs)

    def _pop_component(self, name):
        for component in self._components:
            if component.name == name:
                self._components.remove(component)
                return component
        return None

    def get_free_component(self):
        for component in self._components:
            if not component.win:
                return component

    def remove_component(self, component):
        self._components.remove(component)
        component.destroy()
