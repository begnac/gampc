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
        'action-copy': (GObject.SIGNAL_RUN_FIRST, None, ()),
        'action-paste': (GObject.SIGNAL_RUN_FIRST, None, ()),
        'action-special': (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs, focusable=True, css_name='editablelabel')

        self.label = Gtk.Label(halign=Gtk.Align.START)
        self.add_named(self.label, 'label')

        self.entry = None

        self.gesture = Gtk.GestureClick()
        self.gesture.connect('released', self.released_cb)
        self.add_controller(self.gesture)

        self.focus = Gtk.EventControllerFocus()
        self.focus.connect('leave', self.leave_cb)
        self.add_controller(self.focus)

        self.shortcut = Gtk.ShortcutController()
        self.add_controller(self.shortcut)
        trigger = Gtk.AlternativeTrigger.new(Gtk.KeyvalTrigger(keyval=Gdk.KEY_Return, modifiers=Gdk.ModifierType.NO_MODIFIER_MASK),
                                             Gtk.KeyvalTrigger(keyval=Gdk.KEY_KP_Enter, modifiers=Gdk.ModifierType.NO_MODIFIER_MASK))
        self.shortcut.add_shortcut(Gtk.Shortcut(trigger=trigger, action=Gtk.CallbackAction.new(self._start_editing)))
        trigger = Gtk.KeyvalTrigger(keyval=Gdk.KEY_Escape, modifiers=Gdk.ModifierType.NO_MODIFIER_MASK)
        self.shortcut.add_shortcut(Gtk.Shortcut(trigger=trigger, action=Gtk.CallbackAction.new(self._quit_editing)))
        trigger = Gtk.KeyvalTrigger(keyval=Gdk.KEY_c, modifiers=Gdk.ModifierType.CONTROL_MASK)
        self.shortcut.add_shortcut(Gtk.Shortcut(trigger=trigger, action=Gtk.CallbackAction.new(self._signal), arguments=GLib.Variant('s', 'copy')))
        trigger = Gtk.KeyvalTrigger(keyval=Gdk.KEY_v, modifiers=Gdk.ModifierType.CONTROL_MASK)
        self.shortcut.add_shortcut(Gtk.Shortcut(trigger=trigger, action=Gtk.CallbackAction.new(self._signal), arguments=GLib.Variant('s', 'paste')))
        trigger = Gtk.KeyvalTrigger(keyval=Gdk.KEY_z, modifiers=Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK)
        self.shortcut.add_shortcut(Gtk.Shortcut(trigger=trigger, action=Gtk.CallbackAction.new(self._signal), arguments=GLib.Variant('s', 'special')))

    @staticmethod
    def released_cb(controller, n, x, y):
        if misc.get_modifier_state() & Gdk.ModifierType.CONTROL_MASK:
            controller.get_widget().start_editing()

    @staticmethod
    def activate_cb(widget):
        widget.get_parent().stop_editing(True)

    @staticmethod
    def leave_cb(focus):
        widget = focus.get_widget()
        GLib.idle_add(widget.stop_editing, True)

    def set_label(self, label):
        self.label.set_label(str(label))

    @staticmethod
    def _start_editing(self, arg):
        self.start_editing()

    @staticmethod
    def _quit_editing(self, arg):
        self.stop_editing(False)

    @staticmethod
    def _signal(self, arg):
        self.emit(f'action-{arg.unpack()}')

    def start_editing(self):
        if self.entry is not None:
            return
        self.entry = Gtk.Text()
        self.add_named(self.entry, 'entry')
        self.entry.connect('activate', self.activate_cb)
        self.entry.set_text(self.label.get_label())
        self.set_visible_child_name('entry')
        self.entry.grab_focus()
        self.add_css_class('editing')

    def stop_editing(self, commit):
        if self.entry is None:
            return
        if commit and self.entry.get_text() != self.label.get_label():
            self.label.set_label(self.entry.get_text())
            self.emit('edited', self.entry.get_text())
        self.set_visible_child_name('label')
        self.remove(self.entry)
        self.entry = None
        self.remove_css_class('editing')
        self.grab_focus()

    def grab_focus(self):
        if self.entry is None:
            return super().grab_focus()
        else:
            return self.entry.grab_focus()
