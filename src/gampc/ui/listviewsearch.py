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


from gi.repository import Gdk
from gi.repository import Gtk


class ListViewSearch(Gtk.SearchEntry):
    def __init__(self):
        super().__init__()
        self.popover = None
        controller = Gtk.ShortcutController()
        controller.add_shortcut(Gtk.Shortcut(trigger=Gtk.KeyvalTrigger(keyval=Gdk.KEY_Up, modifiers=Gdk.ModifierType(0)), action=Gtk.SignalAction(signal_name='previous-match')))
        controller.add_shortcut(Gtk.Shortcut(trigger=Gtk.KeyvalTrigger(keyval=Gdk.KEY_Down, modifiers=Gdk.ModifierType(0)), action=Gtk.SignalAction(signal_name='next-match')))
        self.add_controller(controller)

    def setup(self, widget, test_func):
        if self.popover is not None:
            raise RuntimeError

        self.popover = Gtk.Popover(has_arrow=False, halign=Gtk.Align.START)
        self.popover.set_parent(widget)
        self.popover.set_child(self)

        self.connect('activate', self.do_search, widget, True, True, test_func)
        self.connect('next-match', self.do_search, widget, True, False, test_func)
        self.connect('previous-match', self.do_search, widget, False, False, test_func)
        self.connect('search-changed', self.do_search, widget, None, True, test_func)
        self.connect('stop-search', self.stop_search_cb)

        search_action = Gtk.CallbackAction.new(self.search_action_cb)
        search_trigger = Gtk.KeyvalTrigger(keyval=Gdk.KEY_f, modifiers=Gdk.ModifierType.CONTROL_MASK)
        search_shortcut = Gtk.Shortcut(trigger=search_trigger, action=search_action)
        self.search_controller = Gtk.ShortcutController()
        self.search_controller.add_shortcut(search_shortcut)

        widget.add_controller(self.search_controller)

    def cleanup(self):
        if self.popover is None:
            raise RuntimeError
        widget = self.popover.get_parent()
        self.popover.unparent()

        widget.remove_controller(self.search_controller)
        del self.search_controller
        self.popover = None

    def search_action_cb(self, widget, param):
        self.popover.popup()
        found, i, self.base = Gtk.BitsetIter.init_first(widget.get_model().get_selection())
        if not found:
            self.base = 0
        self.pos = self.base
        self.up = True

    @staticmethod
    def do_search(self, widget, up, from_base, test_func):
        if up is None:
            up = self.up
        else:
            self.up = up

        if from_base:
            pos = self.base
        elif up:
            pos = self.pos + 1
        else:
            pos = self.pos - 1

        text = self.get_text()
        model = widget.get_model()
        n = len(model)

        for i in range(n):
            j = (pos + i if up else pos - i) % n
            if test_func(text, model[j]):
                widget.scroll_to(j, Gtk.ListScrollFlags.FOCUS | Gtk.ListScrollFlags.SELECT, None)
                self.remove_css_class('error')
                self.grab_focus()
                self.pos = j
                if not from_base:
                    self.base = j
                return
        self.add_css_class('error')

    @staticmethod
    def stop_search_cb(self):
        self.popover.popdown()
