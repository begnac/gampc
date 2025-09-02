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


from gi.repository import Gtk

from ..util import cleanup
from ..util import config
from ..util import misc

from ..ui import contextmenu
from ..ui import listviewsearch


class WidgetWithEntry(cleanup.CleanupSignalMixin, Gtk.Box):
    def __init__(self, main, activate_cb):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.main = main
        self.entry = Gtk.Entry(hexpand=True)

        self.append(self.main)
        self.append(self.entry)
        self.connect_clean(self.entry, 'activate', activate_cb, main)

    def grab_focus(self):
        return self.entry.grab_focus()


class WidgetWithPaned(contextmenu.ContextMenuActionMixin, cleanup.CleanupSignalMixin, Gtk.Paned):
    def __init__(self, main, config, model, factory, **kwargs):
        self.main = main
        self.config = config
        self.left_selection = model

        self.left_view = Gtk.ListView(model=self.left_selection, factory=factory, tab_behavior=Gtk.ListTabBehavior.ITEM)
        self.left = Gtk.ScrolledWindow(child=self.left_view)
        self.left_view_search = listviewsearch.ListViewSearch(self.left_view, self.left_view_search_test)

        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, position=config['position'], start_child=self.left, end_child=main, focusable=False, **kwargs)

        self.left_selection_pos = []
        self.connect_clean(self.left_selection, 'selection-changed', self.left_selection_changed_cb)
        self.connect('notify::position', self.__class__.notify_position_cb)

        self.add_cleanup_below(self.left_view_search)

    def left_selection_changed_cb(self, selection, position, n_items):
        self.left_selection_pos = list(misc.get_selection(selection))

    def notify_position_cb(self, param):
        self.config['position'] = self.get_position()

    @staticmethod
    def get_paned_config():
        return config.Dict(position=config.Item(int, default=100, is_valid=lambda value: value >= 50))

    def grab_focus(self):
        return self.left_view.grab_focus()
