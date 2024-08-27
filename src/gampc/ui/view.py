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
from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import Gtk

import re
import ampd

from ..util import actions
from ..util import item
from ..util import misc

from . import contextmenu
from . import dnd
from . import editable
from . import listviewsearch
from . import dialog


class ItemFactory(Gtk.SignalListItemFactory):
    def __init__(self, name):
        super().__init__()

        self.name = name

        self.binders = {}
        self.binders['value'] = (self.value_binder, name)
        self.binders['duplicate'] = (self.duplicate_binder,)

        self.connect('setup', self.setup_cb)
        self.connect('bind', self.bind_cb)
        self.connect('unbind', self.unbind_cb)
        # self.connect('teardown', self.teardown_cb)

    @staticmethod
    def setup_cb(self, listitem):
        listitem.set_child(self.make_widget())

    @staticmethod
    def bind_cb(self, listitem):
        widget = listitem.get_child()
        widget.pos = listitem.get_position()
        self.bind(widget, listitem.get_item())

    @staticmethod
    def unbind_cb(self, listitem):
        self.unbind(listitem.get_child(), listitem.get_item())

    # @staticmethod
    # def teardown_cb(self, listitem):
    #     pass

    def bind(self, widget, item):
        for binder, *args in self.binders.values():
            binder(widget, item, *args)
        item.connect('notify', self.notify_item_cb, widget)

    def unbind(self, widget, item):
        item.disconnect_by_func(self.notify_item_cb)

    def notify_item_cb(self, item, param, widget):
        binder, *args = self.binders[param.name]
        binder(widget, item, *args)

    @staticmethod
    def value_binder(widget, item, name):
        widget.set_label(item.get_field(name))

    @staticmethod
    def duplicate_binder(widget, item):
        if item.duplicate is None:
            suffix = None
        else:
            suffix = str(item.duplicate % 64)
        misc.add_unique_css_class(widget.get_parent(), 'duplicate', suffix)


class LabelItemFactory(ItemFactory):
    @staticmethod
    def make_widget():
        return Gtk.Label(halign=Gtk.Align.START)


class EditableItemFactory(ItemFactory):
    def __init__(self, name, always_editable=False):
        super().__init__(name)
        self.always_editable = always_editable

    def make_widget(self):
        return editable.EditableLabel(always_editable=self.always_editable)

    def bind(self, widget, item):
        super().bind(widget, item)
        widget.connect('edited', self.label_edited_cb, item, self.name)

    def unbind(self, widget, item):
        super().unbind(widget, item)
        widget.disconnect_by_func(self.label_edited_cb)

    @staticmethod
    def label_edited_cb(widget, item, name):
        item.value[name] = widget.get_text()
        item.value = item.value


class FieldItemColumn(Gtk.ColumnViewColumn):
    def __init__(self, field, *, sortable, **kwargs):
        self.name = field.name

        super().__init__(**kwargs)

        field.bind_property('title', self, 'title', GObject.BindingFlags.SYNC_CREATE)
        field.bind_property('visible', self, 'visible', GObject.BindingFlags.SYNC_CREATE)
        field.bind_property('width', self, 'fixed-width', GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.BIDIRECTIONAL)

        self.set_resizable(True)

        if sortable:
            sorter = Gtk.CustomSorter.new(self.sort_func, self.name)
            self.set_sorter(sorter)

    @staticmethod
    def sort_func(item1, item2, name):
        s1 = item1.get_field(name)
        s2 = item2.get_field(name)
        return Gtk.Ordering.LARGER if s1 > s2 else Gtk.Ordering.SMALLER if s1 < s2 else Gtk.Ordering.EQUAL


def clean_shortcuts(widget):
    if widget is None:   # Very odd but can happen.  Gtk bug?
        return
    for controller in list(widget.observe_controllers()):
        if isinstance(controller, Gtk.ShortcutController):
            new_controller = Gtk.ShortcutController()
            changed = False
            for shortcut in controller:
                trigger = shortcut.get_trigger()
                if isinstance(trigger, Gtk.KeyvalTrigger) and \
                   trigger.get_modifiers() & Gdk.ModifierType.CONTROL_MASK and \
                   trigger.get_keyval() in (Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_Left, Gdk.KEY_Right, ):
                    changed = True
                else:
                    new_controller.add_shortcut(shortcut)
            if changed:
                widget.remove_controller(controller)
                widget.add_controller(new_controller)


def clean_shortcuts_below(widget):
    clean_shortcuts(widget)
    for child in widget:
        clean_shortcuts_below(child)


class ItemView(Gtk.ColumnView):
    sortable = GObject.Property(type=bool, default=False)
    visible_titles = GObject.Property(type=bool, default=True)

    def __init__(self, fields, factory_factory, **kwargs):
        self.fields = fields
        super().__init__(show_row_separators=True, show_column_separators=True, **kwargs)
        self.add_css_class('data-table')

        self.rows = self.get_last_child()
        self.rows_model = self.rows.observe_children()
        self.rows_model.connect('items-changed', lambda model, p, r, a: [clean_shortcuts(row_widget) for row_widget in model[p:p + a]])

        self.columns = {field.name: FieldItemColumn(field, sortable=self.sortable, factory=factory_factory(field.name)) for field in fields.fields.values()}
        for name in fields.order:
            self.append_column(self.columns[name.get_string()])

        self.bind_property('visible-titles', self.get_first_child(), 'visible', GObject.BindingFlags.SYNC_CREATE)
        self.get_columns().connect('items-changed', self.columns_changed_cb)
        self.fields.order.connect('items-changed', self.fields_order_changed_cb)

    def cleanup(self):
        self.fields.order.disconnect_by_func(self.fields_order_changed_cb)
        self.get_columns().disconnect_by_func(self.columns_changed_cb)
        for col in list(self.get_columns()):
            self.remove_column(col)

    def columns_changed_cb(self, columns, position, removed, added):
        self.fields.order.handler_block_by_func(self.fields_order_changed_cb)
        self.fields.order[position:position + removed] = [Gtk.StringObject.new(col.name) for col in columns[position:position + added]]
        self.fields.order.handler_unblock_by_func(self.fields_order_changed_cb)

    def fields_order_changed_cb(self, order, position, removed, added):
        columns = self.get_columns()
        columns.handler_block_by_func(self.columns_changed_cb)
        for col in list(columns[position:position + removed]):
            self.remove_column(col)
        for i in range(position, position + added):
            self.insert_column(i, self.columns[order[i].get_string()])
        columns.handler_unblock_by_func(self.columns_changed_cb)


class View(Gtk.Box):
    filtering = GObject.Property(type=bool, default=False)

    def __init__(self, fields, factory_factory, *, sortable, selection_model=Gtk.MultiSelection):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.filter_filter = Gtk.CustomFilter()
        self.filter_filter.set_filter_func(self.filter_func)

        self.filter_item = item.Item(value={})
        self.filter_store = Gio.ListStore()
        self.filter_store_selection = Gtk.NoSelection(model=self.filter_store)
        self.filter_view = ItemView(fields, self.filter_factory_factory, sortable=False, model=self.filter_store_selection)
        self.filter_view.add_css_class('filter')
        self.scrolled_filter_view = Gtk.ScrolledWindow(child=self.filter_view, focusable=False, vscrollbar_policy=Gtk.PolicyType.NEVER)
        self.scrolled_filter_view.get_hscrollbar().set_visible(False)
        self.append(self.scrolled_filter_view)
        self.filter_item.connect('notify::value', self.notify_filter_cb)

        self.item_store_selection = selection_model()
        self.item_view = ItemView(fields, factory_factory, sortable=sortable, model=self.item_store_selection, vexpand=True, enable_rubberband=False)
        self.item_view.add_css_class('items')
        self.scrolled_item_view = Gtk.ScrolledWindow(child=self.item_view, focusable=False)
        self.scrolled_item_view.get_hadjustment().bind_property('value', self.scrolled_filter_view.get_hadjustment(), 'value', GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)
        self.append(self.scrolled_item_view)

        self.item_store = Gio.ListStore(item_type=item.Item)
        self.item_store_filter = Gtk.FilterListModel(model=self.item_store)
        if sortable:
            self.item_store_selection.set_model(Gtk.SortListModel(model=self.item_store_filter, sorter=self.item_view.get_sorter()))
        else:
            self.item_store_selection.set_model(self.item_store_filter)

        clean_shortcuts_below(self)

        self.bind_property('filtering', self.filter_view, 'visible-titles', GObject.BindingFlags.SYNC_CREATE)
        self.bind_property('filtering', self.item_view, 'visible-titles', GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.INVERT_BOOLEAN)

        self.view_search = listviewsearch.ListViewSearch(self.item_view.rows, lambda text, item: any(text.lower() in item.get_field(name).lower() for name in fields.fields))

        self.connect('notify::filtering', self.notify_filtering_cb)

    def cleanup(self):
        self.filter_item.disconnect_by_func(self.notify_filter_cb)
        self.filter_filter.set_filter_func(None)
        self.filter_view.cleanup()
        self.item_store.remove_all()
        self.item_view.cleanup()
        self.view_search.cleanup()

    def filter_factory_factory(self, name):
        return EditableItemFactory(name, always_editable=True)

    def notify_filter_cb(self, item, param):
        self.filter_filter.changed(Gtk.FilterChange.DIFFERENT)

    @staticmethod
    def notify_filtering_cb(self, param):
        if self.filtering:
            self.filter_store.append(self.filter_item)
            self.item_store_filter.set_filter(self.filter_filter)
        else:
            self.filter_store.remove(0)
            self.item_store_filter.set_filter(None)

    def filter_func(self, item):
        for name, value in self.filter_item.value.items():
            if re.search(value, item.get_field(name), re.IGNORECASE) is None:
                return False
        return True

    def _get_selection(self):
        return misc.get_selection(self.item_store_selection)

    def get_selection(self):
        return list(self._get_selection())

    def get_selection_items(self):
        return list(map(lambda i: self.item_store_selection[i], self._get_selection()))

    # def get_filenames(self, selection):
    #     if selection:
    #         return list(map(lambda i: self.item_store_selection[i].file, self._get_selection()))
    #     else:
    #         return list(map(lambda item: item.file, self.item_store_selection))


class ItemViewInterface:
    def __init__(self, content_from_items, content_formats=None, add_items=None, remove_items=None):
        self.content_from_items = content_from_items
        self.content_formats = content_formats
        self.add_items = add_items
        self.remove_items = remove_items


class ViewWithContextMenu(contextmenu.ContextMenuMixin, View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_to_context_menu(self.generate_view_actions(), 'view', _("View actions"))

    def generate_view_actions(self):
        yield actions.PropertyActionInfo('filtering', self, _("Filter view"), ['<Control><Shift>f'])
        # util.resource.MenuAction('edit/global', 'itemlist.save', _("Save"), ['<Control>s']),
        # util.resource.MenuAction('edit/global', 'itemlist.reset', _("Reset"), ['<Control>r']),


class ViewWithCopy(ViewWithContextMenu):
    def __init__(self, *args, interface, **kwargs):
        super().__init__(*args, **kwargs)
        self.interface = interface

        self.add_to_context_menu(self.generate_editing_actions(), 'view-edit', _("Edit"))

        self.drag_source = dnd.ListDragSource(interface, actions=Gdk.DragAction.COPY)
        self.item_view.rows.add_controller(self.drag_source)

    def cleanup(self):
        del self.interface
        self.item_view.rows.remove_controller(self.drag_source)
        del self.drag_source
        super().cleanup()

    def generate_editing_actions(self):
        yield actions.ActionInfo('copy', self.action_copy_cb, _("Copy"), ['<Control>c'])

    def action_copy_cb(self, action, parameter):
        self.copy_items(self.get_selection_items())

    def copy_items(self, items):
        self.get_clipboard().set_content(self.interface.content_from_items(items))


class ViewWithCopyPaste(ViewWithCopy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, sortable=False, **kwargs)

        self.connect('notify::filtering', self.check_editable)

        self.drop_target = dnd.ListDropTarget(self.interface)
        self.item_view.rows.add_controller(self.drop_target)

        self.set_editable(True)

    def cleanup(self):
        self.disconnect_by_func(self.check_editable)
        self.item_view.rows.remove_controller(self.drop_target)
        del self.drop_target
        super().cleanup()

    def get_editable(self):
        return self._editable

    def set_editable(self, editable):
        self._editable = editable
        self.check_editable()

    def check_editable(self, *args):
        editable = self._editable and not self.filtering
        actions = self.actions['view-edit']
        for name in actions.list_actions():
            if name != 'copy':
                actions.lookup_action(name).set_enabled(editable)
        self.drag_source.set_actions(Gdk.DragAction.COPY | Gdk.DragAction.MOVE if editable else Gdk.DragAction.COPY)

    def generate_editing_actions(self):
        yield actions.ActionInfo('cut', self.action_cut_cb, _("Cut"), ['<Control>x'])
        yield from super().generate_editing_actions()
        paste_after = actions.ActionInfo('paste', self.action_paste_cb, _("Paste after"), ['<Control>v'], True, parameter_format='b')
        yield paste_after
        yield paste_after.derive(_("Paste before"), ['<Control>b'], False)
        yield actions.ActionInfo('delete', self.action_cut_cb, _("Delete"), ['Delete'])

    def action_cut_cb(self, action, parameter):
        items = self.get_selection_items()
        self.copy_items(items)
        self.interface.remove_items(items)

    def action_delete_cb(self, action, parameter):
        self.interface.remove_items(self.get_selection_items())

    def action_paste_cb(self, action, parameter):
        row = self.item_view.rows.get_focus_child()
        if row is None:
            return
        pos = row.get_first_child().get_first_child().pos
        if parameter.unpack():
            pos += 1
        self.get_clipboard().read_value_async(item.ItemKeyTransfer, 0, None, self.action_paste_finish_cb, pos)

    def action_paste_finish_cb(self, clipboard, result, pos):
        values = clipboard.read_value_finish(result).values
        if values is not None:
            self.interface.add_items(values, pos)


class ViewWithCopyPasteSongs(ViewWithCopyPaste):
    def __init__(self, *args, separator_file, **kwargs):
        super().__init__(*args, **kwargs)
        self.separator_file = separator_file

    def generate_editing_actions(self):
        yield from super().generate_editing_actions()
        yield actions.ActionInfo('add-separator', self.action_add_separator_cb, _("Add separator"))
        yield actions.ActionInfo('add-url', self.action_add_url_cb, _("Add URL or filename"))

    # def generate_special_actions(self):
    #     yield actions.ActionInfo('delete-file', self.action_delete_file_cb, _("Move files to trash"), ['<Control>Delete'])

    def action_add_separator_cb(self, action, parameter):
        selection = self.get_selection()
        if selection:
            pos = selection[0]
        else:
            return
        self.interface.add_items([self.separator_file], pos)

    @ampd.task
    async def action_add_url_cb(self, action, parameter):
        selection = self.get_selection()
        if selection:
            pos = selection[0]
        else:
            return
        dialog_ = dialog.TextDialogAsync(transient_for=self.get_root(), decorated=False, text='http://')
        url = await dialog_.run()
        if url:
            self.interface.add_items([url], pos)

    # def action_delete_file_cb(self, action, parameter):
    #     store, paths = self.treeview.get_selection().get_selected_rows()
    #     deleted = [self.store.get_record(self.store.get_iter(p)) for p in paths]
    #     if deleted:
    #         dialog = Gtk.Dialog(parent=self.get_window(), title=_("Move to trash"))
    #         dialog.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
    #         dialog.add_button(_("_OK"), Gtk.ResponseType.OK)
    #         dialog.get_content_area().add(Gtk.Label(label='\n\t'.join([_("Move these files to the trash bin?")] + [song.file for song in deleted])))
    #         reply = dialog.run()
    #         dialog.destroy()
    #         if reply != Gtk.ResponseType.OK:
    #             return
    #         for song in deleted:
    #             if song._gfile is not None:
    #                 song._gfile.trash()
    #                 song._status = self.RECORD_MODIFIED
