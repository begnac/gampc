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

from ..util import unit

from ..ui import dnd


def load_theme_css(dark, theme_css_provider, app_css_provider):
    theme_css_provider.load_named('Adwaita', 'dark' if dark else None)

    filter_background = 'blue' if dark else 'pink'

    css = ''

    css += f'''
    columnview.filter > listview > row {{
      background: blue;
      color: white;
    }}
    '''

    css += '''
    columnview > listview > row > cell:focus-visible {
      background: green;
    }
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

    app_css_provider.load_from_string(css)


PLAYING_CSS = '''
columnview.song-by-{name} > listview > row > cell.{name}-{value} {{
  background: rgba(128,128,128,0.2);
  font-style: italic;
  font-weight: bold;
}}
'''


def load_playing_css(song, playing_css_provider):
    css = ''
    if 'file' in song:
        css += PLAYING_CSS.format(name='key', value=song['file'].encode().hex())
    if 'Id' in song:
        css += PLAYING_CSS.format(name='Id', value=song['Id'])

    playing_css_provider.load_from_string(css)


class __unit__(unit.Unit):
    def __init__(self, manager):
        super().__init__(manager)
        self.require('persistent')
        self.require('server')

        self.theme_css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.theme_css_provider, Gtk.STYLE_PROVIDER_PRIORITY_SETTINGS)

        self.app_theme_css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.app_theme_css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.unit_persistent.connect('notify::dark', self.notify_dark_cb, self.theme_css_provider, self.app_theme_css_provider)
        load_theme_css(self.unit_persistent.dark, self.theme_css_provider, self.app_theme_css_provider)

        self.playing_css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.playing_css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.unit_server.ampd_server_properties.connect('notify::current-song', self.notify_current_song_cb, self.playing_css_provider)
        load_playing_css(self.unit_server.ampd_server_properties.current_song, self.playing_css_provider)

    @staticmethod
    def notify_dark_cb(persistent, pspec, theme_css_provider, app_css_provider):
        load_theme_css(persistent.dark, theme_css_provider, app_css_provider)

    @staticmethod
    def notify_current_song_cb(server_properties, pspec, playing_css_provider):
        load_playing_css(server_properties.current_song, playing_css_provider)
