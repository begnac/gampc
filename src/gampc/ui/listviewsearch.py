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
    def __init__(self, widget, test_func):
        super().__init__()
        self.widget = widget
        self.test_func = test_func

        search_action = Gtk.CallbackAction.new(self.search_action_cb)
        search_trigger = Gtk.KeyvalTrigger(keyval=Gdk.KEY_f, modifiers=Gdk.ModifierType.CONTROL_MASK)
        search_shortcut = Gtk.Shortcut(trigger=search_trigger, action=search_action)
        self.search_controller = Gtk.ShortcutController()
        self.search_controller.add_shortcut(search_shortcut)
        widget.add_controller(self.search_controller)

        controller = Gtk.ShortcutController()
        controller.add_shortcut(Gtk.Shortcut(trigger=Gtk.KeyvalTrigger(keyval=Gdk.KEY_Up, modifiers=Gdk.ModifierType(0)), action=Gtk.SignalAction(signal_name='previous-match')))
        controller.add_shortcut(Gtk.Shortcut(trigger=Gtk.KeyvalTrigger(keyval=Gdk.KEY_Down, modifiers=Gdk.ModifierType(0)), action=Gtk.SignalAction(signal_name='next-match')))
        self.add_controller(controller)

        self.popover = Gtk.Popover(has_arrow=False, halign=Gtk.Align.START)
        self.popover.set_child(self)

        # self.connect('activate', self.search_cb, widget, True, True, test_func)
        self.connect('next-match', self.__class__.search_cb, widget, True, False, test_func)
        self.connect('previous-match', self.__class__.search_cb, widget, False, False, test_func)
        self.connect('search-changed', self.__class__.search_cb, widget, None, True, test_func)
        self.connect('stop-search', self.__class__.stop_search_cb)
        self.connect('activate', self.__class__.stop_search_cb)

    def cleanup(self):
        self.widget.remove_controller(self.search_controller)
        del self.search_controller
        self.popover.set_child(None)

    def search_action_cb(self, widget, param):
        self.popover.set_parent(widget)
        self.popover.popup()
        found, i, self.base = Gtk.BitsetIter.init_first(widget.get_model().get_selection())
        if not found:
            self.base = 0
        self.pos = self.base
        self.up = True

    def search_cb(self, widget, up, from_base, test_func):
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
                widget.scroll_to(j, Gtk.ListScrollFlags.SELECT, None)
                self.remove_css_class('error')
                self.grab_focus()
                self.pos = j
                if not from_base:
                    self.base = j
                return
        self.add_css_class('error')

    def stop_search_cb(self):
        self.popover.popdown()
        self.popover.unparent()
        self.widget.scroll_to(self.pos, Gtk.ListScrollFlags.FOCUS, None)
