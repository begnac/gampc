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
from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import Gtk

from ..util import misc


class EditableLabel(Gtk.Stack):
    __gsignals__ = {
        'edited': (GObject.SIGNAL_RUN_FIRST, None, (str,)),
    }

    def __init__(self, *, always_editable=False, **kwargs):
        self.always_editable = always_editable

        super().__init__(**kwargs, focusable=True, css_name='editablelabel')

        self.label = Gtk.Label()
        self.entry = Gtk.Entry(text=self.label.get_label(), css_name='label', visible=False)
        self.add_named(self.label, 'label')
        self.add_named(self.entry, 'entry')
        self.set_visible_child(self.label)

        self.focus = Gtk.EventControllerFocus()
        self.focus.connect('leave', self.leave_cb)
        self.add_controller(self.focus)
        # self.focus.connect('enter', lambda *args: print(args, self.get_focus_child()))

        self.shortcut = Gtk.ShortcutController()
        self.add_controller(self.shortcut)
        self.shortcut.add_shortcut(Gtk.Shortcut(trigger=Gtk.KeyvalTrigger(keyval=Gdk.KEY_Return, modifiers=Gdk.ModifierType.NO_MODIFIER_MASK), action=Gtk.CallbackAction.new(lambda self, arg: self.start_editing())))

        self.editing_shortcuts = Gtk.ShortcutController()
        # self.shortcut.add_shortcut(Gtk.Shortcut(trigger=Gtk.KeyvalTrigger(keyval=Gdk.KEY_Return, modifiers=Gdk.ModifierType.NO_MODIFIER_MASK), action=Gtk.CallbackAction.new(lambda self, arg: self.done_editing())))
        self.shortcut.add_shortcut(Gtk.Shortcut(trigger=Gtk.KeyvalTrigger(keyval=Gdk.KEY_Escape, modifiers=Gdk.ModifierType.NO_MODIFIER_MASK), action=Gtk.CallbackAction.new(lambda self, arg: self.cancel_editing())))

        # self.gesture = Gtk.GestureClick()
        # self.gesture.connect('pressed', self.pressed_cb)
        # self.add_controller(self.gesture)

    def set_label(self, label):
        self.label.set_label(label)

    def start_editing(self):
        if self.entry.get_visible():
            return
        self.entry.set_text(self.label.get_label())
        self.set_visible_child(self.entry)
        self.entry.grab_focus()
        self.add_css_class('editing')

    def done_editing(self):
        print(888)
        if self.entry is None:
            return
        text = self.entry.get_text()
        print(text)
        if text != self.label.get_label():
            self.label.set_label(text)
            print(3463563456)
            GLib.timeout_add(0, lambda: self.emit('edited', text))
        self._stop_editing()

    def cancel_editing(self):
        if self.entry is None:
            return
        self._stop_editing()

    def _stop_editing(self):
        self.set_visible_child(self.label)
        self.remove_css_class('editing')
        self.get_parent().grab_focus()

    @staticmethod
    def leave_cb(focus):
        print(777777777777777777777777777)
        focus.get_widget().done_editing()

    @staticmethod
    def pressed_cb(click, *args):
        if misc.get_modifier_state() & Gdk.ModifierType.CONTROL_MASK and \
           click.set_state(Gtk.EventSequenceState.CLAIMED):
            click.get_widget().start_editing()





class xEditableLabel(Gtk.EditableLabel):
    label = GObject.Property(type=str, default='')

    __gsignals__ = {
        'edited': (GObject.SIGNAL_RUN_FIRST, None, (str,)),
    }

    def __init__(self, *, always_editable, **kwargs):
        self.always_editable = always_editable

        super().__init__(editable=always_editable, **kwargs)

        self.shortcut = Gtk.ShortcutController()
        self.add_controller(self.shortcut)
        self.shortcut.add_shortcut(Gtk.Shortcut(trigger=Gtk.KeyvalTrigger(keyval=Gdk.KEY_Return, modifiers=Gdk.ModifierType(0)), action=Gtk.CallbackAction.new(lambda self, arg: self.really_start_editing())))

        self.gesture = Gtk.GestureClick()
        self.add_controller(self.gesture)
        self.gesture.connect('pressed', self.pressed_cb)

        self.connect('notify::editing', self.notify_editing_cb)
        self.bind_property('label', self, 'text', GObject.BindingFlags.SYNC_CREATE)

    def set_label(self, label):
        self.label = label

    def really_start_editing(self):
        self.set_editable(True)
        self.start_editing()

    @staticmethod
    def notify_editing_cb(self, pspec):
        if not self.get_editing():
            self.set_editable(self.always_editable)
            if self.get_text() != self.label:
                self.emit('edited', self.get_text())

    @staticmethod
    def pressed_cb(click, *args):
        if misc.get_modifier_state() & Gdk.ModifierType.CONTROL_MASK and \
           click.set_state(Gtk.EventSequenceState.CLAIMED):
            click.get_widget().really_start_editing()
