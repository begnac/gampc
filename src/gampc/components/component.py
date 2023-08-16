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
from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import Gtk

import types

from ..util import resource
from ..util import unit
from ..util.logger import logger
from ..ui import entry


class Component(GObject.Object):
    use_resources = []

    status = GObject.Property()
    full_title = GObject.Property(type=str)

    def __init__(self, unit, *, name=None):
        super().__init__(full_title=unit.title)
        self.focus_widget = None
        self.unit = unit
        self.name = name or unit.name
        self.manager = unit.manager
        self.config = self.unit.config
        self.ampd = self.unit.ampd.sub_executor()
        self.signal_handlers = []
        self.actions_dict = {}
        self.action_aggregator_dict = {}
        self.window_signals = {}

        self.actions = self.add_actions_provider(self.name)

        self.status_binding = self.bind_property('status', self, 'full-title', GObject.BindingFlags(0), lambda x, y: "{} [{}]".format(unit.title, self.status) if self.status else unit.title)

        self.signal_handler_connect(unit.unit_server.ampd_client, 'client-connected', self.client_connected_cb)
        if self.ampd.get_is_connected():
            self.client_connected_cb(unit.unit_server.ampd_client)

    def __del__(self):
        logger.debug('Deleting {}'.format(self))

    def shutdown(self):
        if self.get_window() is not None:
            raise RuntimeError
        self.signal_handlers_disconnect()
        # self.widget.destroy()
        self.status_binding.unbind()
        for action_aggregator in self.action_aggregator_dict.values():
            self.manager.remove_aggregator(action_aggregator)
        self.ampd.close()
        del self.window_signals
        del self.actions
        del self.actions_dict
        del self.action_aggregator_dict

    def get_window(self):
        root = self.widget.get_root()
        return root if isinstance(root, Gtk.Window) else None

    def add_actions_provider(self, name):
        actions = self.actions_dict[name] = Gio.SimpleActionGroup()
        action_aggregator = self.action_aggregator_dict[name] = resource.ActionAggregator([name + '.action'], actions, lambda f: types.MethodType(f, self), self.unit.unit_persistent)
        self.unit.manager.add_aggregator(action_aggregator)
        return actions

    def signal_handler_connect(self, target, *args):
        handler = target.connect(*args)
        self.signal_handlers.append((target, handler))

    def signal_handlers_disconnect(self):
        for target, handler in self.signal_handlers:
            target.disconnect(handler)
        self.signal_handlers = []

    def insert_action_groups(self, widget):
        for prefix, actions in self.actions_dict.items():
            widget.insert_action_group(prefix, actions)

    def remove_action_groups(self, widget):
        for prefix in self.actions_dict:
            widget.insert_action_group(prefix, None)

    def setup_context_menu(self, name, widget):
        controller = Gtk.GestureClick(button=3)
        controller.connect('pressed', self.context_menu_pressed_cb, name)
        widget.add_controller(controller)
        # for signal in ('pressed', 'released', 'stopped', 'unpaired-release', 'begin', 'cancel', 'end', 'sequence-state-changed', 'update'):
        #     controller.connect(signal, lambda *args: print(args[-1], args[:-1]), signal)

    def context_menu_pressed_cb(self, controller, n_press, x, y, name):
        if name not in self.unit.menu_aggregators:
            return
        menu_model = self.unit.menu_aggregators[name].menu
        if menu_model.get_n_items() == 0:
            return
        rectangle = Gdk.Rectangle()
        rectangle.x = x
        rectangle.y = y
        popup = Gtk.PopoverMenu(menu_model=menu_model, pointing_to=rectangle)
        self.insert_action_groups(popup)
        popup.set_parent(controller.get_widget())
        popup.popup()

    @staticmethod
    def client_connected_cb(client):
        pass


class ComponentMixinPaned:
    def __init__(self, unit):
        super().__init__(unit)
        self.left_view = Gtk.ListView(factory=self.get_left_factory())
        self.left_scrolled = Gtk.ScrolledWindow()
        self.left_scrolled.set_child(self.left_view)
        # self.left_treeview.set_search_equal_func(lambda store, col, key, i: key.lower() not in store.get_value(i, col).lower())

        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, position=self.config.pane_separator._get())
        self.paned.connect('notify::position', self.paned_notify_position_cb, self.config)
        self.paned.set_start_child(self.left_scrolled)
        self.paned.set_end_child(self.widget)
        self.widget = self.paned

        self.setup_context_menu(f'{self.name}.left-context', self.left_view)

    @staticmethod
    def paned_notify_position_cb(paned, param, config):
        config.pane_separator._set(paned.get_position())


class ComponentMixinEntry:
    def __init__(self, unit):
        super().__init__(unit)

        self.focus_widget = self.entry = entry.Entry(unit_misc=unit.unit_misc)
        self.signal_handler_connect(self.entry, 'activate', self.entry_activate_cb)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(self.widget)
        box.append(self.entry)
        self.widget = box


class UnitMixinComponent(unit.UnitMixinConfig, unit.UnitMixinServer):
    def __init__(self, name, manager, *, menus=[]):
        self.REQUIRED_UNITS = ['component', 'persistent'] + self.REQUIRED_UNITS
        super().__init__(name, manager)
        self.menu_aggregators = {}

        self.unit_component.register_component_factory(self.name, self.new_component)
        self.add_resource('app.menu', resource.MenuAction('components/components',
                                                          f'app.component-start("{self.name}")',
                                                          self.title,
                                                          ['<Alt>' + self.key, '<Control><Alt>' + self.key]))

        for menu in menus:
            self.setup_menu(self.name, menu, self.COMPONENT_CLASS.use_resources)

    def shutdown(self):
        for aggregator in self.menu_aggregators.values():
            self.manager.remove_aggregator(aggregator)
        del self.menu_aggregators
        self.unit_component.unregister_component_factory(self.name)
        super().shutdown()

    def new_component(self):
        return self.COMPONENT_CLASS(self)

    def setup_menu(self, name, kind, providers=[]):
        aggregator = resource.MenuAggregator([f'{provider}.{kind}.menu' for provider in [name] + providers])
        self.manager.add_aggregator(aggregator)
        self.menu_aggregators[f'{name}.{kind}'] = aggregator


class UnitMixinPanedComponent(UnitMixinComponent, unit.UnitMixinConfig):
    def __init__(self, name, manager, **kwargs):
        super().__init__(name, manager, **kwargs)
        self.config.pane_separator._get(default=100)
