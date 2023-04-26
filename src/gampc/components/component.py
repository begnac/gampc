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
from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import Gtk

import types

from ..util import data
from ..util import resource
from ..util import unit
from ..util.logger import logger


class Component(Gtk.Bin):
    action_prefix = 'mod'
    use_resources = []

    status = GObject.Property()
    full_title = GObject.Property(type=str)

    def __init__(self, unit):
        super().__init__(visible=True, full_title=unit.title)
        self.unit = unit
        self.config = self.unit.config
        self.ampd = self.unit.ampd.sub_executor()
        self.signal_handlers = []
        self.window_actions = Gio.SimpleActionGroup()
        self.window_signals = {}
        self.win = None

        self.action_aggregator = resource.ActionAggregator([provider + '.action' for provider in [unit.name] + self.use_resources], self.window_actions, lambda f: types.MethodType(f, self), self.unit.unit_persistent)
        unit.manager.add_aggregator(self.action_aggregator)

        self.bind_property('status', self, 'full-title', GObject.BindingFlags(0), lambda x, y: "{} [{}]".format(unit.title, self.status) if self.status else unit.title)

        self.connect('destroy', self.__destroy_cb)
        self.signal_handler_connect(unit.unit_server.ampd_client, 'client-connected', self.client_connected_cb)
        if self.ampd.get_is_connected():
            self.client_connected_cb(unit.unit_server.ampd_client)

    def __del__(self):
        logger.debug('Deleting {}'.format(self))

    @staticmethod
    def __destroy_cb(self):
        self.signal_handlers_disconnect()
        self.ampd.close()
        del self.action_aggregator
        del self.window_signals
        del self.window_actions

    def signal_handler_connect(self, target, *args):
        handler = target.connect(*args)
        self.signal_handlers.append((target, handler))

    def signal_handlers_disconnect(self):
        for target, handler in self.signal_handlers:
            target.disconnect(handler)
        self.signal_handlers = []

    def setup_context_menu(self, name, widget):
        if name not in self.unit.menu_aggregators:
            return
        model = self.unit.menu_aggregators[name].menu
        if model.get_n_items() == 0:
            return
        menu = Gtk.Menu.new_from_model(model)
        menu.insert_action_group(self.action_prefix, self.window_actions)
        widget.connect('button-press-event', self.context_menu_button_press_event_cb, menu)

    @staticmethod
    def context_menu_button_press_event_cb(widget, event, menu):
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
            menu.popup_at_pointer(event)
            return True
        return False

    @staticmethod
    def client_connected_cb(client):
        pass


class PanedComponent(Component):
    def __init__(self, unit):
        super().__init__(unit)

        self.left_store = self.init_left_store()
        self.left_treeview = Gtk.TreeView(model=self.left_store, visible=True)
        self.scrolled_left_treeview = Gtk.ScrolledWindow(visible=True)
        self.scrolled_left_treeview.add(self.left_treeview)
        self.left_treeview.get_selection().connect('changed', self.left_treeview_selection_changed_cb)
        self.left_treeview.set_search_equal_func(lambda store, col, key, i: key.lower() not in store.get_value(i, col).lower())

        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, position=self.config.pane_separator._get(), visible=True)
        self.paned.connect('notify::position', self.paned_notify_position_cb)
        self.paned.add1(self.scrolled_left_treeview)
        super().add(self.paned)

        self.setup_context_menu('.'.join([unit.name, 'left-context']), self.left_treeview)

        self.starting = True
        self.connect('map', self.__map_cb)

    @staticmethod
    def __map_cb(self):
        if self.starting:
            self.left_treeview.grab_focus()
            self.starting = False

    def paned_notify_position_cb(self, *args):
        self.config.pane_separator._set(self.paned.get_position())

    def left_store_set_rows(self, rows):
        data.store_set_rows(self.left_store, rows, lambda i, name: self.left_store.set_value(i, 0, name))

    def add(self, child):
        self.paned.add2(child)

    def remove(self, child):
        self.paned.remove2(child)


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
        full_name = '.'.join([name, kind])
        aggregator = resource.MenuAggregator(['.'.join([full_name, 'menu'])] + ['.'.join([provider, kind, 'menu']) for provider in providers])
        self.manager.add_aggregator(aggregator)
        self.menu_aggregators[full_name] = aggregator


class UnitMixinPanedComponent(UnitMixinComponent, unit.UnitMixinConfig):
    def __init__(self, name, manager, **kwargs):
        super().__init__(name, manager, **kwargs)
        self.config.pane_separator._get(default=100)
