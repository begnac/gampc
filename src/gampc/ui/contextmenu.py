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


from gi.repository import Gio
from gi.repository import Gtk

from ..util import action
from ..util import cleanup
from ..util import misc


class ContextMenuActionMixin(cleanup.CleanupBaseMixin):
    def __init__(self, *args, **kwargs):
        self.context_menu = Gio.Menu()
        self.menus = {}
        self.actions = {}

        super().__init__(*args, **kwargs)

        controller = Gtk.GestureClick(button=3)
        controller.connect('pressed', self.context_menu_pressed_cb)
        self.add_controller(controller)

    def cleanup(self):
        for prefix in self.actions:
            self.insert_action_group(prefix, None)
        del self.actions
        super().cleanup()

    def add_context_menu_actions(self, generator, prefix, label, *, submenu=False, protect=None, target_menu=None):
        assert prefix not in self.actions
        family = action.ActionInfoFamily(generator, prefix, label)
        self.actions[prefix] = family.get_action_group(protect=protect)
        self.insert_action_group(prefix, self.actions[prefix])
        self.add_controller(family.get_shortcut_controller())

        if target_menu is None:
            target_menu = self.context_menu
        self.menus[prefix] = family.get_menu()
        if submenu:
            target_menu.append_submenu(label, self.menus[prefix])
        else:
            target_menu.append_section(None, self.menus[prefix])

    @staticmethod
    def context_menu_pressed_cb(controller, n_press, x, y):
        self = controller.get_widget()
        if self.context_menu.get_n_items() == 0:
            return
        menu = Gtk.PopoverMenu(menu_model=self.context_menu, flags=Gtk.PopoverMenuFlags.NESTED, has_arrow=False, pointing_to=misc.Rectangle(x, y), halign=Gtk.Align.START)
        menu.set_parent(self)
        menu.popup()
