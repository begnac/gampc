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


from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import Gtk

from ..util import item


class EditManager(GObject.Object):
    __gsignals__ = {
        'edited': (GObject.SIGNAL_RUN_FIRST, None, (object, object)),
    }


class EditableLabel(Gtk.Box):
    item_position = GObject.Property(type=int)

    def __init__(self, edit_manager, **kwargs):
        super().__init__(**kwargs, css_name='editablelabel')

        self.edit_manager = edit_manager

        self.text = None
        self.label = Gtk.Label()
        self.append(self.label)

        self.shortcut = Gtk.ShortcutController()
        trigger = Gtk.KeyvalTrigger(keyval=Gdk.KEY_c, modifiers=Gdk.ModifierType.CONTROL_MASK)
        self.shortcut.add_shortcut(Gtk.Shortcut(trigger=trigger, action=Gtk.CallbackAction.new(self.copy_cb)))
        trigger = Gtk.KeyvalTrigger(keyval=Gdk.KEY_v, modifiers=Gdk.ModifierType.CONTROL_MASK)
        self.shortcut.add_shortcut(Gtk.Shortcut(trigger=trigger, action=Gtk.CallbackAction.new(self.paste_cb)))
        trigger = Gtk.KeyvalTrigger(keyval=Gdk.KEY_Return, modifiers=Gdk.ModifierType.NO_MODIFIER_MASK)
        self.shortcut.add_shortcut(Gtk.Shortcut(trigger=trigger, action=Gtk.CallbackAction.new(self.start_editing_cb)))

        self.click = Gtk.GestureClick(button=1, propagation_phase=Gtk.PropagationPhase.CAPTURE)
        self.click.connect('pressed', self.click_pressed_cb)

        self.connect('map', self.__class__.map_cb)
        self.connect('unmap', self.__class__.unmap_cb)

    def get_label(self):
        return self.label.get_label()

    def set_label(self, label):
        self.label.set_label(label)

    def map_cb(self):
        parent = self.get_parent()
        parent.add_controller(self.shortcut)
        parent.add_controller(self.click)

    def unmap_cb(self):
        parent = self.get_parent()
        parent.remove_controller(self.shortcut)
        parent.remove_controller(self.click)

    def start_editing(self):
        assert self.text is None
        self.remove(self.label)
        self.text = Gtk.Text(text=self.label.get_label(), hexpand=True)
        self.append(self.text)

        self.text.connect('activate', self.finish_editing_cb)

        shortcut = Gtk.ShortcutController()
        trigger = Gtk.KeyvalTrigger(keyval=Gdk.KEY_Escape, modifiers=Gdk.ModifierType.NO_MODIFIER_MASK)
        shortcut.add_shortcut(Gtk.Shortcut(trigger=trigger, action=Gtk.CallbackAction.new(self.abort_editing_cb)))
        self.text.add_controller(shortcut)

        self.text_focus = Gtk.EventControllerFocus()
        self.text_focus.connect('leave', self.finish_editing_cb)
        self.text.add_controller(self.text_focus)

        self.text.grab_focus()

    def stop_editing(self, keep):
        if keep and self.text.get_text() != self.get_label():
            self.edit_manager.emit('edited', self, {self.get_name(): self.text.get_text()})
        self.text.remove_controller(self.text_focus)
        del self.text_focus
        self.get_parent().grab_focus()
        self.remove(self.text)
        self.text = None
        self.append(self.label)
        return False

    @staticmethod
    def start_editing_cb(parent, data):
        parent.get_first_child().start_editing()

    def finish_editing_cb(self, *args):
        assert self.text is not None
        GLib.timeout_add(0, self.stop_editing, True)

    def abort_editing_cb(self, *args):
        assert self.text is not None
        GLib.timeout_add(0, self.stop_editing, False)

    @staticmethod
    def copy_cb(parent, data):
        self = parent.get_first_child()
        self.get_clipboard().set_content(item.PartialTransfer({self.get_name(): self.get_label()}).get_content())
        return True

    @staticmethod
    def paste_cb(parent, data):
        self = parent.get_first_child()
        self.get_clipboard().read_value_async(item.PartialTransfer, 0, None, self.paste_finish_cb)
        return False

    def paste_finish_cb(self, clipboard, result):
        if not result.had_error():
            self.edit_manager.emit('edited', self, clipboard.read_value_finish(result).value)

    @staticmethod
    def click_pressed_cb(click, n_press, x, y):
        if click.get_current_event_state() & Gdk.ModifierType.CONTROL_MASK:
            self = click.get_widget().get_first_child()
            if self.text is None:
                click.set_state(Gtk.EventSequenceState.CLAIMED)
                self.start_editing()
