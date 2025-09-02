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
from gi.repository import Gtk

from ..util.misc import FactoryBase

from . import compound


class Node(GObject.Object):
    expanded = GObject.Property(type=bool, default=True)

    def __init__(self, name=None, path=None, *, model_factory=Gio.ListStore, expanded=False, **kwargs):
        super().__init__(expanded=expanded)
        self.name = name
        self.path = [] if path is None else path + [name]
        self.__dict__.update(kwargs)
        self.model = model_factory and model_factory()
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
        return node.model

    def merge(self, store, names, fill, create_node, update_node=None):
        n = len(names)
        for pos in range(n):
            while pos < len(store) and store[pos].name < names[pos]:
                store.remove(pos)
            if pos < len(store) and store[pos].name == names[pos]:
                if update_node:
                    update_node(store[pos])
                if fill:
                    self.fill_node(store[pos])
                else:
                    store[pos].ready = False
            else:
                store.insert(pos, create_node(names[pos]))
        store[n:] = []


class TreeListItemFactory(FactoryBase):
    def setup_cb(self, listitem):
        box = Gtk.Box(spacing=4)
        child = Gtk.TreeExpander(child=box, focusable=False)
        child.icon = Gtk.Image()
        child.label = Gtk.Label()
        box.append(child.icon)
        box.append(child.label)
        listitem.set_child(child)

    def bind_cb(self, listitem):
        child = listitem.get_child()
        row = listitem.get_item()
        node = row.get_item()
        row.bind_property('expanded', node, 'expanded')
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


class WidgetWithPanedTreeList(compound.WidgetWithPaned):
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

    @staticmethod
    def left_view_search_test(text, row):
        return text.lower() in row.get_item().name.lower()
