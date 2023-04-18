# coding: utf-8
#
# Graphical Asynchronous Music Player Client
#
# Copyright (C) 2015-2022 Itaï BEN YAACOV
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

import ampd

from ..util import resource
from ..util import unit
from ..util.logger import logger
from ..ui import headerbar
from ..ui import logging


class Window(Gtk.ApplicationWindow):
    DEFAULT_TITLE = 'GAMPC'

    def __init__(self, app, unit):
        super().__init__(application=app, show_menubar=True)
        self.unit = unit
        self.is_fullscreen = False
        self.component = None

        self.set_default_size(self.unit.config.width._get(default=1000),
                              self.unit.config.height._get(default=600))
        if self.unit.config.maximized._get(default=False):
            self.maximize()

        self.connect('destroy', self.destroy_cb)

        self.unit.unit_server.connect('notify::current-song', self.notify_current_song_cb)
        self.unit.unit_server.ampd_server_properties.connect('notify::state', self.update_title)
        self.unit.unit_server.connect('notify::server-label', self.update_subtitle)

        self.main = Gtk.Box(visible=True, orientation=Gtk.Orientation.VERTICAL)
        self.info_box = Gtk.Box(visible=True, orientation=Gtk.Orientation.VERTICAL)
        self.main.pack_end(self.info_box, False, False, 0)
        self.add(self.main)

        self.headerbar = headerbar.HeaderBar()
        self.set_titlebar(self.headerbar)

        self.unit.unit_persistent.bind_property('protect-active', self.headerbar.option_buttons, 'sensitive', GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.INVERT_BOOLEAN)

        self.unit.unit_server.ampd_server_properties.bind_property('state', self.headerbar.playback_buttons, 'playing', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: value == 'play')
        self.unit.unit_server.ampd_server_properties.bind_property('volume', self.headerbar.volume_button, 'value', GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)
        self.unit.unit_server.ampd_server_properties.bind_property('volume', self.headerbar.volume_button, 'sensitive', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: value != -1)
        self.unit.unit_persistent.bind_property('protect-requested', self.headerbar.protected_image, 'visible', GObject.BindingFlags.SYNC_CREATE)
        self.unit.unit_server.ampd_server_properties.bind_property('bitrate', self.headerbar.bitrate_label, 'label', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: ' [{kbps}kbps]'.format(kbps=value) if value else '')

        self.unit.unit_server.ampd_server_properties.bind_property('duration', self.headerbar.time_scale, 'duration', GObject.BindingFlags.SYNC_CREATE)
        self.unit.unit_server.ampd_server_properties.bind_property('elapsed', self.headerbar.time_scale, 'elapsed', GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)

        self.unit.unit_server.ampd_server_properties.connect('notify::state', self.set_time_scale_sensitive)
        self.unit.unit_persistent.connect('notify::protect-active', self.set_time_scale_sensitive)

        self.add_action(resource.Action('toggle-fullscreen', self.action_toggle_fullscreen_cb))
        self.add_action(resource.Action('volume-popup', self.action_volume_popup_cb))

        self.logging_handler = logging.Handeler(self.info_box, self.unit.config.message_timeout._get() * 1000)
        logger.addHandler(self.logging_handler)
        self.update_title()
        self.update_subtitle()

    @staticmethod
    def destroy_cb(self):
        logger.debug("Destroying window: {}".format(self))
        self.change_component(None)
        logger.removeHandler(self.logging_handler)
        self.logging_handler.shutdown()
        self.remove_action('toggle-fullscreen')
        self.remove_action('volume-popup')
        self.unit.unit_server.disconnect_by_func(self.update_subtitle)
        self.unit.unit_server.ampd_server_properties.disconnect_by_func(self.update_title)
        self.unit.unit_server.disconnect_by_func(self.notify_current_song_cb)

    def change_component(self, component):
        if self.component is not None:
            self.component.disconnect_by_func(self.update_subtitle)
            self.component.disconnect_by_func(self.update_title)
            self.main.remove(self.component)
            self.component.set_window()
        self.component = component
        if self.component is not None:
            self.component.set_window(self)
            self.main.pack_start(component, True, True, 0)
            self.component.connect('notify::title-extra', self.update_title)
            self.component.connect('notify::full-title', self.update_subtitle)
        self.update_subtitle()

    def set_time_scale_sensitive(self, *args):
        if self.unit.unit_persistent.protect_active or self.unit.unit_server.ampd_server_properties.state not in ('play', 'pause'):
            self.headerbar.time_scale.set_sensitive(False)
        else:
            self.headerbar.time_scale.set_sensitive(True)

    def notify_current_song_cb(self, *args):
        self.headerbar.time_scale.break_interaction()
        self.update_title()

    def update_title(self, *args):
        if self.unit.unit_server.ampd_server_properties.state == 'play':
            window_title = _("{artist} / {title}")
        elif self.unit.unit_server.ampd_server_properties.state == 'pause':
            window_title = _("{artist} / {title} (paused)")
        else:
            window_title = self.DEFAULT_TITLE
        artist = self.unit.unit_server.current_song.get('Artist', _("Unknown Artist"))
        title = self.unit.unit_server.current_song.get('Title', _("Unknown Title"))
        self.headerbar.set_title(window_title.format(artist=artist, title=title))

    def update_subtitle(self, *args):
        chunks = []
        if self.component:
            chunks.append(self.component.full_title)
        if self.unit.unit_server.server_label:
            chunks.append(self.unit.unit_server.server_label)
        self.headerbar.set_subtitle(' / '.join(chunks))

    def do_configure_event(self, event):
        if not self.is_fullscreen:
            self.unit.config.width._set(event.width)
            self.unit.config.height._set(event.height)
            self.unit.config.maximized._set(self.is_maximized())
        Gtk.ApplicationWindow.do_configure_event(self, event)

    def action_toggle_fullscreen_cb(self, *args):
        if self.is_fullscreen:
            self.unfullscreen()
        else:
            self.fullscreen()

    def action_volume_popup_cb(self, action, parameter):
        if self.volume_button.is_sensitive() and not self.volume_button.get_popup().get_mapped():
            self.volume_button.emit('popup')
        else:
            self.volume_button.emit('popdown')

    def do_window_state_event(self, event):
        self.is_fullscreen = bool(event.new_window_state & Gdk.WindowState.FULLSCREEN)
        self.set_show_menubar(not self.is_fullscreen)
        self.headerbar.set_visible(not self.is_fullscreen)
        return Gtk.ApplicationWindow.do_window_state_event(self, event)


class __unit__(unit.UnitMixinConfig, unit.UnitMixinServer, unit.Unit):
    REQUIRED_UNITS = ['persistent']

    def __init__(self, manager, name):
        super().__init__(manager, name)
        self.config.message_timeout._get(default=5)

    def new_window(self, app):
        return Window(app, self)
