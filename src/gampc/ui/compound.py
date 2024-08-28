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

from ..util import misc

from . import contextmenu
from . import listviewsearch


class WidgetWithEntry(Gtk.Box):
    def __init__(self, main, activate_cb):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.main = main
        self.entry = Gtk.Entry()
        self.activate_cb = activate_cb

        self.append(self.main)
        self.append(self.entry)
        self.entry.connect('activate', activate_cb)

    def cleanup(self):
        self.entry.disconnect_by_func(self.activate_cb)
        self.main.cleanup()

    def grab_focus(self):
        self.entry.grab_focus()


class TreeItemFactory(Gtk.SignalListItemFactory):
    def __init__(self):
        super().__init__()

        self.connect('setup', self.setup_cb)
        self.connect('bind', self.bind_cb)
        # self.connect('unbind', self.unbind_cb)
        # self.connect('teardown', self.teardown_cb)

    @staticmethod
    def setup_cb(self, listitem):
        box = Gtk.Box(spacing=4)
        child = Gtk.TreeExpander(child=box, focusable=False)
        child.icon = Gtk.Image()
        child.label = Gtk.Label()
        box.append(child.icon)
        box.append(child.label)
        listitem.set_child(child)

    @staticmethod
    def bind_cb(self, listitem):
        child = listitem.get_child()
        row = listitem.get_item()
        node = row.get_item()
        child.icon.set_from_icon_name(node.icon)
        if node.modified:
            child.label.set_label('* ' + node.name)
            child.label.set_css_classes(['modified'])
        else:
            child.label.set_label(node.name)
            child.label.set_css_classes([])
        child.set_list_row(row)

    # @staticmethod
    # def unbind_cb(self, listitem):
    #     pass

    # @staticmethod
    # def teardown_cb(self, listitem):
    #     self.labels.remove(listitem.label)


class ScrolledListView(contextmenu.ContextMenuMixin, Gtk.ScrolledWindow):
    def __init__(self, **kwargs):
        self.view = Gtk.ListView(**kwargs)
        self.view_search = listviewsearch.ListViewSearch(self.view, lambda text, row: text.lower() in row.get_item().name.lower())
        super().__init__(child=self.view)


class WidgetWithPaned(Gtk.Paned):
    def __init__(self, main, config, model, factory, **kwargs):
        self.main = main
        self.config = config
        self.left_selection = model

        self.left = ScrolledListView(model=self.left_selection, factory=factory)

        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, position=config._get(), start_child=self.left, end_child=main, **kwargs)

        self.left_selection_pos = []
        self.left_selected_item = None
        self.left_selection.connect('selection-changed', self.left_selection_changed_cb)
        self.connect('notify::position', self.paned_notify_position_cb, config)

    def cleanup(self):
        self.main.cleanup()
        self.left.view_search.cleanup()
        self.left_selection.disconnect_by_func(self.left_selection_changed_cb)

    def grab_focus(self):
        self.left.view.grab_focus()

    def left_selection_changed_cb(self, selection, position, n_items):
        self.left_selection_pos = list(misc.get_selection(selection))
        if len(self.left_selection_pos) == 1:
            self.left_selected_item = selection[self.left_selection_pos[0]].get_item()
        else:
            self.left_selected_item = None

    @staticmethod
    def paned_notify_position_cb(paned, param, config):
        config._set(paned.get_position())


class WidgetWithPanedTreeList(WidgetWithPaned):
    def __init__(self, main, config, root_model, **kwargs):
        self.left_store = Gtk.TreeListModel.new(root_model, False, False, lambda node: node.expose())
        model = Gtk.MultiSelection(model=self.left_store)
        model.select_item(0, True)

        super().__init__(main, config, model, TreeItemFactory(), **kwargs)

        self.left.view.connect('activate', self.left_view_activate_cb)

    @staticmethod
    def left_view_activate_cb(view, position):
        row = view.get_model()[position]
        if row.is_expandable():
            row.set_expanded(not row.get_expanded())
