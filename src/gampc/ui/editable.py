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

from ..util import item


class EditManager(GObject.Object):
    __gsignals__ = {
        'edited': (GObject.SIGNAL_RUN_FIRST, None, (object, object)),
    }


class EditableLabel(Gtk.EditableLabel):
    def __init__(self, edit_manager, **kwargs):
        super().__init__(**kwargs, focusable=True, css_name='editablelabel')

        self.edit_manager = edit_manager

        self.shortcut = Gtk.ShortcutController()
        self.add_controller(self.shortcut)
        trigger = Gtk.KeyvalTrigger(keyval=Gdk.KEY_c, modifiers=Gdk.ModifierType.CONTROL_MASK)
        self.shortcut.add_shortcut(Gtk.Shortcut(trigger=trigger, action=Gtk.CallbackAction.new(self.__class__.copy_cb)))
        trigger = Gtk.KeyvalTrigger(keyval=Gdk.KEY_v, modifiers=Gdk.ModifierType.CONTROL_MASK)
        self.shortcut.add_shortcut(Gtk.Shortcut(trigger=trigger, action=Gtk.CallbackAction.new(self.__class__.paste_cb)))

        self.connect('notify::editing', self.__class__.notify_editing_cb)

    def set_label(self, label):
        self.set_text(label)

    def notify_editing_cb(self, param):
        if self.get_editing():
            self.old_text = self.get_text()
        else:
            if self.get_text() != self.old_text:
                self.edit_manager.emit('edited', self, {self.get_name(): self.get_text()})
            del self.old_text

    def copy_cb(self, args):
        self.get_clipboard().set_content(item.PartialTransfer({self.get_name(): self.get_text()}).get_content())
        return True

    def paste_cb(self, args):
        self.get_clipboard().read_value_async(item.PartialTransfer, 0, None, self.paste_finish_cb)
        return False

    def paste_finish_cb(self, clipboard, result):
        if not result.had_error():
            self.edit_manager.emit('edited', self, clipboard.read_value_finish(result).value)
