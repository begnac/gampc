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
from ..util import unit
from ..util.logger import logger


class Component(Gtk.Bin):
    title = None
    name = None
    key = None
    action_prefix = 'mod'
    use_resources = []

    status = GObject.Property()
    full_title = GObject.Property(type=str)

    def __init__(self, unit):
        super().__init__(visible=True, full_title=self.title)
        self.unit = unit
        self.config = self.unit.config
        self.ampd = self.unit.ampd.sub_executor()
        self.signal_handlers = []
        self.actions = Gio.SimpleActionGroup()
        self.signals = {}
        self.win = None

        self.action_aggregator = unit.manager.create_aggregator(self.name + '.action', self.action_added_cb, self.action_removed_cb,
                                                                also_wants=[provider + '.action' for provider in self.use_resources])

        self.bind_property('status', self, 'full-title', GObject.BindingFlags(0), lambda x, y: "{} [{}]".format(self.title, self.status) if self.status else self.title)

        self.connect('destroy', self.__destroy_cb)
        self.signal_handler_connect(unit.unit_server.ampd_client, 'client-connected', self.client_connected_cb)
        if self.ampd.get_is_connected():
            self.client_connected_cb(unit.unit_server.ampd_client)

    def __del__(self):
        logger.debug('Deleting {}'.format(self))

    def set_window(self, win=None):
        if self.win is not None:
            self.win.insert_action_group(self.action_prefix, None)
            for cb in self.signals.values():
                self.win.disconnect_by_func(cb)
        self.win = win
        if self.win is not None:
            for name, cb in self.signals.items():
                self.win.connect(name, cb)
            self.win.insert_action_group(self.action_prefix, self.actions)

    @staticmethod
    def __destroy_cb(self):
        self.signal_handlers_disconnect()
        self.ampd.close()
        del self.action_aggregator
        del self.signals
        del self.actions

    def signal_handler_connect(self, target, *args):
        handler = target.connect(*args)
        self.signal_handlers.append((target, handler))

    def signal_handlers_disconnect(self):
        for target, handler in self.signal_handlers:
            target.disconnect(handler)
        self.signal_handlers = []

    def setup_context_menu(self, name, widget):
        if name not in self.unit.menus or self.unit.menus[name].get_n_items() == 0:
            return
        menu = Gtk.Menu.new_from_model(self.unit.menus[name])
        menu.insert_action_group(self.action_prefix, self.actions)
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

    def action_added_cb(self, manager, action):
        self.actions.add_action(action.generate(lambda f: types.MethodType(f, self), self.unit.unit_persistent))

    def action_removed_cb(self, manager, action):
        self.actions.remove_action(action.name)


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

        self.setup_context_menu('.'.join([self.name, 'left-context']), self.left_treeview)

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
    def __init__(self, name, manager):
        self.REQUIRED_UNITS = ['component', 'persistent'] + self.REQUIRED_UNITS
        super().__init__(name, manager)
        self.unit_component.register_component_class(self.MODULE_CLASS, self)
        self.aggregators = []
        self.menus = {}

    def shutdown(self):
        for aggregator in reversed(self.aggregators):
            self.manager.remove_aggregator(aggregator)
        del self.aggregators
        self.unit_component.unregister_component_class(self.MODULE_CLASS)
        super().shutdown()

    def setup_menu(self, name, kind, providers=[]):
        full_name = '.'.join([name, kind])
        self.menus[full_name] = Gio.Menu()
        aggregator = self.manager.create_aggregator('.'.join([full_name, 'menu']), self.menu_item_added_cb, self.menu_item_removed_cb, full_name,
                                                    also_wants=['.'.join([provider, kind, 'menu']) for provider in providers])
        self.aggregators.append(aggregator)

    def menu_item_added_cb(self, aggregator, menu_item, name):
        menu_item.insert_into(self.menus[name])

    def menu_item_removed_cb(self, aggregator, menu_item, name):
        menu_item.remove_from(self.menus[name])


class UnitMixinPanedComponent(UnitMixinComponent, unit.UnitMixinConfig):
    def __init__(self, name, manager):
        super().__init__(name, manager)
        self.config.pane_separator._get(default=100)
