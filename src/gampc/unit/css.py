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

from ..util import cleanup
from ..util import unit

from ..ui import dnd


class __unit__(cleanup.CleanupCssMixin, unit.Unit):
    def __init__(self, manager):
        super().__init__(manager)
        self.require('persistent')

        self.theme_css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.theme_css_provider, Gtk.STYLE_PROVIDER_PRIORITY_SETTINGS)

        self.connect_clean(self.unit_persistent, 'notify::dark', self.notify_dark_cb)
        self.load_css()

    def notify_dark_cb(self, persistent, pspec):
        self.load_css()

    def load_css(self):
        dark = self.unit_persistent.dark

        self.theme_css_provider.load_named('Adwaita', 'dark' if dark else None)

        edit_background = 'green' if dark else 'yellow'
        filter_background = 'blue' if dark else 'pink'

        css = ''

        css += f'''
        columnview.filter > listview > row {{
          background: {filter_background};
        }}
        '''

        css += f'''
        columnview > listview > row > cell:focus-visible {{
          background: {edit_background};
        }}
        '''

        css += '''
        editablelabel.editing {
          background-color: rgb(45,45,45);
          border-bottom-color: rgb(27,27,27);
          border-left-color: rgb(27,27,27);
          border-right-color: rgb(27,27,27);
          border-top-color: rgb(27,27,27);
          color: rgb(255,255,255);
        }
        ''' if dark else '''
        editablelabel.editing > label > text {
          background-color: rgb(255,255,255);
          border-bottom-color: rgb(205,199,194);
          border-left-color: rgb(205,199,194);
          border-right-color: rgb(205,199,194);
          border-top-color: rgb(205,199,194);
          color: rgb(0,0,0);
        }
        '''

        css += dnd.get_css(dark)

        N = 4
        for d in range(N ** 3):
            colors = [((d // (N ** k)) % N) * 255 / (N - 1) for k in range(3)]
            css += f'''
              columnview > listview > row > cell.duplicate-{d} {{
              background: rgba({colors[0]},{colors[1]},{colors[2]},0.5);
            }}
            '''

        self.css_provider.load_from_string(css)
