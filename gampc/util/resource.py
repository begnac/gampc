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
from gi.repository import Gio
from gi.repository import GLib


class MenuPathBase(GObject.Object):
    ATTRIBUTE_NAME = 'menu-path-name'

    def __init__(self, path, label=None):
        GObject.Object.__init__(self)
        self.path = path
        *self.path_names, self.name = path.split('/')
        self.label = label

    def create_item(self):
        item = Gio.MenuItem.new(label=self.label)
        item.set_attribute_value(self.ATTRIBUTE_NAME, GLib.Variant.new_string(self.name))
        return item

    def insert_into(self, menu):
        submenu = self.find_submenu(menu)
        if self.find_name(submenu, self.name) is not None:
            raise ValueError("Item '{name}' already exists in path '{path}'".format(name=self.name, path=self.path))
        submenu.append_item(self.create_item())

    def remove_from(self, menu):
        submenu = self.find_submenu(menu)
        i = self.find_name(submenu, self.name)
        if i is None:
            raise ValueError("Item '{name}' dose not exists in path '{path}'".format(name=self.name, path=self.path))
        submenu.remove(i)

    def find_submenu(self, menu):
        submenu = menu
        for name in self.path_names:
            i = self.find_name(submenu, name)
            if i is None:
                raise ValueError("Path element '{name}' not found in path '{path}'".format(name=name, path=self.path))
            submenu = submenu.get_item_link(i, Gio.MENU_LINK_SUBMENU) or submenu.get_item_link(i, Gio.MENU_LINK_SECTION)
            if submenu is None:
                raise ValueError("Path element '{name}' is not a submenu or a section in path '{path}'".format(name=name, path=self.path))
        return submenu

    def find_name(self, submenu, name):
        n = submenu.get_n_items()
        for i in range(n):
            item_name = submenu.get_item_attribute_value(i, self.ATTRIBUTE_NAME)
            if item_name and item_name.get_string() == name:
                return i
        return None


class MenuPath(MenuPathBase):
    def __init__(self, path, label=None, *, is_submenu=False, instance=None):
        super().__init__(path, label)
        self.is_submenu = is_submenu
        self.instance = instance

    def create_item(self):
        item = super().create_item()
        submenu = self.instance or Gio.Menu()
        if self.is_submenu:
            item.set_submenu(submenu)
        else:
            item.set_section(submenu)
        return item


class MenuAction(MenuPathBase):
    def create_item(self):
        item = super().create_item()
        item.set_detailed_action(self.name)
        item.set_attribute_value('hidden-when', GLib.Variant.new_string('action-missing'))
        return item


class UserAction(GObject.Object):
    def __init__(self, action, label, path, accels=[], accels_fragile=False):
        GObject.Object.__init__(self)
        self.action = action
        self.path = path
        self.label = label
        self.accels = accels
        self.accels_fragile = accels_fragile

    def get_menu_action(self):
        return MenuAction('{path}/{action}'.format(path=self.path, action=self.action), self.label)


class Action(Gio.SimpleAction):
    def __init__(self, name, activate_cb, *, dangerous=False, protector=None, **kwargs):
        super().__init__(name=name, **kwargs)
        self.connect('activate', activate_cb)
        if dangerous:
            protector.bind_property('protected', self, 'enabled', GObject.BindingFlags.SYNC_CREATE, lambda x, y: not y)


class PropertyAction(Gio.PropertyAction):
    def __init__(self, name, object_, property_name=None, *, dangerous=False, protector=None, **kwargs):
        super().__init__(name=name, object=object_, property_name=property_name or name, **kwargs)
        if dangerous:
            protector.bind_property('protected', self, 'enabled', GObject.BindingFlags.SYNC_CREATE, lambda x, y: not y)


class ActionModelBase(GObject.Object):
    def __init__(self, name, **kwargs):
        GObject.Object.__init__(self)
        self.name = name
        self.kwargs = kwargs

    def get_name(self):
        return self.name


class ActionModel(ActionModelBase):
    def __init__(self, name, activate_cb, **kwargs):
        super().__init__(name, **kwargs)
        self.activate_cb = activate_cb

    def generate(self, decorator, protector):
        return Action(self.name, decorator(self.activate_cb), protector=protector, **self.kwargs)


class PropertyActionModel(ActionModelBase):
    def __init__(self, name, object_, property_name=None, **kwargs):
        super().__init__(name, **kwargs)
        self.object_ = object_
        self.property_name = property_name

    def generate(self, protector, *args):
        return PropertyAction(name=self.name, object_=self.object_, property_name=self.property_name, **self.kwargs)


class ResourceProvider(GObject.Object):
    __gsignals__ = {
        'resource-added': (GObject.SIGNAL_RUN_FIRST, None, (GObject.Object,)),
        'resource-removed': (GObject.SIGNAL_RUN_FIRST, None, (GObject.Object,)),
    }

    def __init__(self, name):
        super().__init__()
        self.name = name
        self._resources = []

    def get_resources(self):
        return self._resources

    def add_resource(self, resource):
        self._resources.append(resource)
        self.emit('resource-added', resource)

    def remove_resource(self, resource):
        self.emit('resource-removed', resource)
        self._resources.remove(resource)

    def add_resources(self, *resources):
        for resource in resources:
            self.add_resource(resource)

    def remove_resources(self, *resources):
        for resource in reversed(resources):
            self.remove_resource(resource)

    def remove_all_resources(self):
        for resource in reversed(self._resources):
            self.remove_resource(resource)


class ResourceAggregator(ResourceProvider):
    def __init__(self, name, also_wants=[]):
        super().__init__(name)
        self._providers = []
        self.also_wants = also_wants

    def link(self, provider):
        self.add_resources(*provider.get_resources())
        provider.connect('resource-added', self.resource_added_cb)
        provider.connect('resource-removed', self.resource_removed_cb)
        self._providers.append(provider)

    def unlink(self, provider):
        self._providers.remove(provider)
        provider.disconnect_by_func(self.resource_added_cb)
        provider.disconnect_by_func(self.resource_removed_cb)
        self.remove_resources(*provider.get_resources())

    def resource_added_cb(self, provider, resource):
        self.add_resource(resource)

    def resource_removed_cb(self, provider, resource):
        self.remove_resource(resource)



# ('\([^']*\)/[^/']*', \('[^']*'\), \(_("[^"]*")\) → (\2, \3, '\1'
# ('\([^']*\)/[^/']*', \([^,]*\), \([^,]*\) → (\2, \3, '\1'
