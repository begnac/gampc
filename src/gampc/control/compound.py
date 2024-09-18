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


class TreeListItemFactory(Gtk.SignalListItemFactory):
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
        if hasattr(node, 'edit_stack'):
            node.edit_stack.connect('notify::modified', self.notify_modified_cb, child.label, node.name)
            self.notify_modified_cb(node.edit_stack, None, child.label, node.name)
        else:
            child.label.set_label(node.name)
        child.icon.set_from_icon_name(node.icon)
        child.set_list_row(row)

    @staticmethod
    def notify_modified_cb(edit_stack, pspec, label, name):
        if edit_stack.modified:
            label.set_label('* ' + name)
            label.set_css_classes(['modified'])
        else:
            label.set_label(name)
            label.set_css_classes([])

    # @staticmethod
    # def unbind_cb(self, listitem):
    #     pass

    # @staticmethod
    # def teardown_cb(self, listitem):
    #     self.labels.remove(listitem.label)


class WidgetWithPaned(contextmenu.ContextMenuActionMixin, cleanup.CleanupSignalMixin, Gtk.Paned):
    def __init__(self, main, config, model, factory, **kwargs):
        self.main = main
        self.config = config
        self.left_selection = model

        self.left_view = Gtk.ListView(model=self.left_selection, factory=factory, tab_behavior=Gtk.ListTabBehavior.ITEM)
        self.left = Gtk.ScrolledWindow(child=self.left_view)
        self.left_view_search = listviewsearch.ListViewSearch(self.left_view, lambda text, row: text.lower() in row.get_item().name.lower())
        misc.remove_control_move_shortcuts_below(self.left_view)

        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, position=config._get(), start_child=self.left, end_child=main, **kwargs, focusable=False)

        self.left_selection_pos = []
        self.connect_clean(self.left_selection, 'selection-changed', self.left_selection_changed_cb)
        self.connect('notify::position', self.paned_notify_position_cb, config)

        self.add_cleanup_below(self.left_view_search)

    def left_selection_changed_cb(self, selection, position, n_items):
        self.left_selection_pos = list(misc.get_selection(selection))

    @staticmethod
    def paned_notify_position_cb(paned, param, config):
        config._set(paned.get_position())

    def grab_focus(self):
        return self.left_view.grab_focus()


class WidgetWithPanedTreeList(WidgetWithPaned):
    def __init__(self, main, config, tree, **kwargs):
        self.left_store = Gtk.TreeListModel.new(tree.root.model, False, False, tree.expose)
        model = Gtk.MultiSelection(model=self.left_store)
        model.select_item(0, True)
        self.left_selected_item = None

        super().__init__(main, config, model, TreeListItemFactory(), **kwargs)

        self.left_view.connect('activate', self.left_view_activate_cb)

    def cleanup(self):
        del self.left_selected_item
        super().cleanup()

    def left_selection_changed_cb(self, selection, position, n_items):
        super().left_selection_changed_cb(selection, position, n_items)
        if len(self.left_selection_pos) == 1:
            self.left_selected_item = selection[self.left_selection_pos[0]].get_item()
        else:
            self.left_selected_item = None

    @staticmethod
    def left_view_activate_cb(view, position):
        row = view.get_model()[position]
        if row.is_expandable():
            row.set_expanded(not row.get_expanded())
