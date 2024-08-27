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
from gi.repository import Gdk
from gi.repository import Gtk

from .. import util


class EditableLabel(Gtk.EditableLabel):
    label = GObject.Property(type=str, default='')

    __gsignals__ = {
        'edited': (GObject.SIGNAL_RUN_FIRST, None, ()),
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
    def notify_editing_cb(self, *args):
        if not self.get_editing():
            self.set_editable(self.always_editable)
            if self.get_text() != self.label:
                self.emit('edited')

    @staticmethod
    def pressed_cb(click, *args):
        if misc.get_modifier_state() & Gdk.ModifierType.CONTROL_MASK and \
           click.set_state(Gtk.EventSequenceState.CLAIMED):
            click.get_widget().really_start_editing()
