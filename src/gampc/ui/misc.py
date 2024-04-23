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
from gi.repository import Gtk


class EditableMixin:
    def __init__(self, *, unit_misc, **kwargs):
        super().__init__(**kwargs)

        self.focus = Gtk.EventControllerFocus()
        self.add_controller(self.focus)
        self.focus.connect('enter', self.focus_cb, unit_misc, True)
        self.focus.connect('leave', self.focus_cb, unit_misc, False)

    @staticmethod
    def focus_cb(controller, unit_misc, block):
        unit_misc.block_fragile_accels = block


class Entry(EditableMixin, Gtk.Entry):
    pass


class EditableLabel(EditableMixin, Gtk.EditableLabel):
    label = GObject.Property(type=str, default='')

    __gsignals__ = {
        'edited': (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, **kwargs):
        super().__init__(editable=True, **kwargs)
        self.connect('notify::editing', self.notify_editing_cb)
        self.bind_property('label', self, 'text', GObject.BindingFlags.SYNC_CREATE)

    @staticmethod
    def notify_editing_cb(self, *args):
        if self.get_text() != self.label:
            self.emit('edited')
