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


def get_accel_trigger(accel):
    parsed, keyval, modifiers = Gtk.accelerator_parse(accel)
    if not parsed:
        raise ValueError(accel)
    return Gtk.KeyvalTrigger(keyval=keyval, modifiers=modifiers)


def get_accels_trigger(accels):
    trigger = get_accel_trigger(accels[0])
    for accel in accels[1:]:
        trigger = Gtk.AlternativeTrigger(first=trigger, second=get_accel_trigger(accel))
    return trigger


class ActionInfo:
    def __init__(self, name, data, label=None, accels=None, arg=None, *, parameter_format=None, state=None, dangerous=False):
        self.name = name
        self.data = data
        self.label = label
        self.accels = accels
        self.arg = None if arg is None else GLib.Variant(parameter_format, arg)

        self.parameter_format = parameter_format
        self.state = state
        self.dangerous = dangerous

    def add_to(self, *args):
        for arg in args:
            arg.add_action_info(self)

    def get_action(self, protect=None):
        if self.data is not None:
            parameter_type = None if self.parameter_format is None else GLib.VariantType.new(self.parameter_format)
            action = Gio.SimpleAction(name=self.name, parameter_type=parameter_type, state=self.state)
            action.connect('activate', self.data)
            if self.dangerous:
                protect(action)
            return action

    def get_shortcut(self, prefix):
        if self.accels is None:
            return None, None
        main = Gtk.Shortcut(trigger=get_accel_trigger(self.accels[0]), action=Gtk.NamedAction.new(f'{prefix}.{self.name}'), arguments=self.arg)
        if len(self.accels) > 1:
            secondary = Gtk.Shortcut(trigger=get_accels_trigger(self.accels[1:]), action=Gtk.NamedAction.new(f'{prefix}.{self.name}'), arguments=self.arg)
        else:
            secondary = None
        return main, secondary

    def get_menu_item(self, prefix):
        if self.label is None:
            return None
        item = Gio.MenuItem.new(self.label, f'{prefix}.{self.name}')
        item.set_attribute_value(Gio.MENU_ATTRIBUTE_TARGET, self.arg)
        return item

    def derive(self, label, accels=None, arg=None):
        return ActionInfo(self.name, None, label, accels, arg, parameter_format=self.parameter_format, dangerous=self.dangerous)

    def __str__(self):
        return f"Action \"{self.name}\""


class PropertyActionInfo(ActionInfo):
    def get_action(self, protect=None):
        if self.data is not None:
            action = Gio.PropertyAction(name=self.name, property_name=self.name, object=self.data)
            if self.dangerous:
                protect(action)
            return action


class ActionInfoFamily:
    def __init__(self, action_infos, prefix=None, label=None):
        self.action_infos = list(action_infos)
        self.prefix = prefix
        self.label = label

    def get_menu(self):
        menu = Gio.Menu()
        for action_info in self.action_infos:
            menu_item = action_info.get_menu_item(self.prefix)
            if menu_item is not None:
                menu.append_item(menu_item)
                menu.append_section(None, Gio.Menu())
        return menu

    def add_to_action_map(self, action_map, protect=None):
        for action_info in self.action_infos:
            action = action_info.get_action(protect)
            if action is not None:
                action_map.add_action(action)

    def get_action_group(self, protect=None):
        action_group = Gio.SimpleActionGroup()
        self.add_to_action_map(action_group, protect)
        return action_group

    def insert_action_group(self, widget, protect=None):
        action_group = self.get_action_group(protect)
        widget.insert_action_group(self.prefix, action_group)
        return action_group

    def add_to_shortcut_controller(self, controller):
        for action_info in self.action_infos:
            shortcut, secondary_shortcut = action_info.get_shortcut(self.prefix)
            if shortcut is not None:
                # Important to add the main shortcut last, for display in menu.
                if secondary_shortcut is not None:
                    controller.add_shortcut(secondary_shortcut)
                controller.add_shortcut(shortcut)

    def get_shortcut_controller(self):
        controller = Gtk.ShortcutController()
        self.add_to_shortcut_controller(controller)
        return controller


class ActionInfoFamiliesMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.action_info_families = []

    def cleanup(self):
        del self.action_info_families
        super().cleanup()
