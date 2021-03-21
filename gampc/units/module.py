# coding: utf-8
#
# Graphical Asynchronous Music Player Client
#
# Copyright (C) 2015 Itaï BEN YAACOV
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


from gampc.util import resource
from gampc.util import unit


class __unit__(unit.Unit):
    REQUIRED_UNITS = ['menubar']

    def __init__(self, name, manager):
        super().__init__(name, manager)
        self._module_classes = {}
        self._modules = []

        self.new_resource_provider('app.menu').add_resources(
            resource.MenuPath('modules/modules', _("Press <Ctrl> for a new instance")),
            resource.MenuPath('modules/current'),
        )

        self.user_action_provider = self.new_resource_provider('app.user-action')
        self.user_action_provider.add_resources(
            resource.UserAction('app.module-stop', _("Stop module"), 'modules/current', ['<Control><Shift>w'])
        )

    def shutdown(self):
        for module in self._modules:
            module.destroy()
        del self._modules
        super().shutdown()

    def register_module_class(self, module_class, *args, **kwargs):
        name = module_class.name
        if name in self._module_classes:
            raise RuntimeError
        user_action = resource.UserAction('app.module-start("{name}")'.format(name=name),
                                          module_class.title, 'modules/modules', ['<Alt>' + module_class.key, '<Control><Alt>' + module_class.key])
        self._module_classes[name] = module_class, args, kwargs, user_action
        self.user_action_provider.add_resource(user_action)

    def unregister_module_class(self, module_class):
        name = module_class.name
        *_, user_action = self._module_classes[name]
        self.user_action_provider.remove_resource(user_action)
        del self._module_classes[name]

    def get_module(self, name, new_instance):
        module = (not new_instance and self._pop_module(name)) or self._new_module(name)
        self._modules.append(module)
        return module

    def _new_module(self, name):
        module_class, args, kwargs, _ = self._module_classes[name]
        return module_class(*args, **kwargs)

    def _pop_module(self, name):
        for module in self._modules:
            if module.name == name:
                self._modules.remove(module)
                return module
        return None

    def get_free_module(self):
        for module in self._modules:
            if not module.win:
                return module

    def remove_module(self, module):
        self._modules.remove(module)
        module.destroy()
