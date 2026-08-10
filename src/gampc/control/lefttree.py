"""Graphical Asynchronous Music Player Client."""

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
from gi.repository import Gtk

from ..util.item import WithItemModelMixin
from ..util.misc import FactoryBase

from . import compound


class Node(WithItemModelMixin, GObject.Object):
    def __init__(self, name=None, path=None, *, icon=None, children=None, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.path = [] if path is None else path + [name]
        self.children = children
        self.icon = icon
        self.rows = []
        self.ready = False

    def __repr__(self):
        return '/'.join(self.path)


class Tree:
    def __init__(self):
        self.root = self.get_root()

    def start(self):
        self.fill_node(self.root)

    def expose(self, node):
        if not node.ready:
            node.ready = True
            self.fill_node(node)
        return node.children

    def merge(self, store, names, fill, create_node, update_node=None):
        for i, name in enumerate(names):
            while i < len(store) and store[i].name < name:
                store.remove(i)
            if i < len(store) and store[i].name == name:
                if update_node:
                    update_node(store[i])
                if fill:
                    self.fill_node(store[i])
                else:
                    store[i].ready = False
            else:
                store.insert(i, create_node(name))
        store[len(names):] = []


class TreeExpander(Gtk.TreeExpander):
    def __init__(self):
        box = Gtk.Box(spacing=4)
        self.icon = Gtk.Image()
        self.label = Gtk.Label()
        box.append(self.icon)
        box.append(self.label)
        super().__init__(child=box)


class TreeListItemFactory(FactoryBase):
    def setup_cb(self, listitem):
        listitem.set_child(TreeExpander())

    def bind_cb(self, listitem):
        child = listitem.get_child()
        row = listitem.get_item()
        node = row.get_item()
        node.rows.append(row)
        if hasattr(node, 'edit_stack'):
            node.edit_stack.connect('notify::modified', self.notify_modified_cb, child.label, node.name)
            self.notify_modified_cb(node.edit_stack, None, child.label, node.name)
        else:
            child.label.set_label(node.name)
        child.icon.set_from_icon_name(node.icon)
        child.set_list_row(row)

    def unbind_cb(self, listitem):
        row = listitem.get_item()
        node = row.get_item()
        node.rows.remove(row)

    @staticmethod
    def notify_modified_cb(edit_stack, pspec, label, name):
        if edit_stack.modified:
            label.set_label('* ' + name)
            label.set_css_classes(['modified'])
        else:
            label.set_label(name)
            label.set_css_classes([])


class WidgetWithPanedTreeList(compound.WidgetWithPaned):
    def __init__(self, main, config, tree, **kwargs):
        left_store = Gtk.TreeListModel.new(tree.root.children, False, False, tree.expose)
        super().__init__(main, config, Gtk.MultiSelection(model=left_store), TreeListItemFactory(), **kwargs)

        selection_filter_model = Gtk.SelectionFilterModel(model=self.left_selection_model)
        map_model = Gtk.MapListModel.new(selection_filter_model, lambda row: row.get_item().item_model)
        flatten_model = Gtk.FlattenListModel(model=map_model)
        main.set_model(flatten_model)

        self.left_selection_model.select_item(0, True)
        self.left_view.connect('activate', self.left_view_activate_cb)
        self.left_selected_item = None

    def left_selection_changed_cb(self, selection, position, n_items):
        super().left_selection_changed_cb(selection, position, n_items)
        if len(self.left_selected_positions) == 1:
            self.left_selected_item = selection[self.left_selected_positions[0]].get_item()
        else:
            self.left_selected_item = None

    @staticmethod
    def left_view_activate_cb(view, position):
        row = view.get_model()[position]
        if row.is_expandable():
            row.set_expanded(not row.get_expanded())

    @staticmethod
    def left_view_search_test(text, row):
        return text.lower() in row.get_item().name.lower()
