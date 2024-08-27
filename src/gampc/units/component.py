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


from gi.repository import GLib
from gi.repository import Gio
from gi.repository import Gtk

from .. import util


class __unit__(util.unit.UnitCssMixin, util.unit.Unit):
    CSS = """
    listview > row > treeexpander > box > label.modified {
      font-style: italic;
      font-weight: bold;
    }
    """

    def __init__(self, *args):
        super().__init__(*args)
        self._registered_components = {}
        self._components = {}

        self.label = _("_Component")
        self.start_family = util.action.ActionInfoFamily(self.generate_start_actions(), 'app', self.label)
        self.stop_family = util.action.ActionInfoFamily(self.generate_stop_actions(), 'app', self.label)

        self.start_menu = Gio.Menu()

        self.menu = Gio.Menu()
        self.menu.append_section(_("Press <Ctrl> for a new instance"), self.start_menu)
        self.menu.append_section(None, self.stop_family.get_menu())
        self.regenerate_start()

    def shutdown(self):
        del self.start_family
        del self.stop_family
        for components in self._components.values():
            for component in components:
                component.shutdown()
        del self._components
        super().shutdown()

    def generate_start_actions(self):
        start = util.action.ActionInfo('component-start', self.component_start_cb, parameter_format='(sb)')
        yield start
        for component in self._registered_components.values():
            yield start.derive(component.title, ['<Alt>' + component.key], arg=GLib.Variant('(sb)', (component.name, False)))
            yield start.derive(None, ['<Control><Alt>' + component.key], arg=GLib.Variant('(sb)', (component.name, True)))

    def generate_stop_actions(self):
        yield util.action.ActionInfo('component-stop', self.component_stop_cb, _("Stop component"), ['<Control><Shift>w'])

    def register_component(self, component):
        if component.name in self._registered_components:
            raise RuntimeError
        self._registered_components[component.name] = component
        self.regenerate_start()

    def unregister_component(self, name):
        del self._registered_components[name]
        self.regenerate_start()

    def regenerate_start(self):
        self.start_family.action_infos = list(self.generate_start_actions())
        self.start_menu.remove_all()
        self.start_menu.append_section(None, self.start_family.get_menu())

    def get_component(self, name, new_instance):
        if not self._components.setdefault(name, []) or new_instance:
            component = self._registered_components[name].new_component()
        else:
            component = self._components[name].pop(0)
        self._components[name].append(component)
        return component

    def get_free_component(self):
        for components in self._components.values():
            for component in components:
                if not component.get_window():
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

    def component_start_cb(self, action, parameter):
        name, new_instance = parameter.unpack()
        component = self.get_component(name, new_instance)
        window = component.get_window()
        if window is None:
            window = Gtk.Application.get_default().get_active_window()
            window.change_component(component)
        window.present()

    def component_stop_cb(self, action, parameter):
        window = Gtk.Application.get_default().get_active_window()
        component = window.component
        if component is not None:
            window.change_component(window.unit.unit_component.get_free_component())
            self.remove_component(component)
