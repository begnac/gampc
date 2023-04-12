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


from gi.repository import GObject, GLib, Gtk, Gdk
import logging

import ampd

from ..util import data
from ..util import resource
from ..util import unit
from ..util.logger import logger


class WindowLoggingHandeler(logging.Handler):
    MAX_INFOBARS = 5

    def __init__(self, box, timeout):
        super().__init__(logging.INFO)
        self.box = box
        self.timeout = timeout
        self.infobars = []

    def remove_infobar(self, infobar, response=None):
        self._remove_infobar(infobar)
        GLib.source_remove(infobar.timeout)

    def remove_infobar_timeout(self, infobar):
        self._remove_infobar(infobar)
        return GLib.SOURCE_REMOVE

    def _remove_infobar(self, infobar):
        self.infobars.remove(infobar)
        self.box.remove(infobar)

    def cull_infobars(self, n = 0):
        while len(self.infobars) > n:
            self.remove_infobar(self.infobars[0])

    def emit(self, record):
        self.cull_infobars(self.MAX_INFOBARS - 1)

        message_type = Gtk.MessageType.ERROR if record.levelno >= 40 else Gtk.MessageType.WARNING if record.levelno >= 30 else Gtk.MessageType.INFO
        message_icon = 'error' if record.levelno >= 40 else 'warning' if record.levelno >= 30 else 'information'
        infobar = Gtk.InfoBar(visible=True, message_type=message_type, show_close_button=True)
        infobar.get_content_area().add(Gtk.Image(visible=True, icon_name='dialog-' + message_icon, icon_size=Gtk.IconSize.LARGE_TOOLBAR))
        infobar.get_content_area().add(Gtk.Label(visible=True, label=record.msg))
        infobar.connect('response', self.remove_infobar)
        infobar.timeout = GLib.timeout_add(self.timeout, self.remove_infobar_timeout, infobar)
        self.box.add(infobar)
        self.infobars.append(infobar)

    def shutdown(self):
        self.cull_infobars()


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

        builder = self.unit.unit_builder.build_ui('window')

        for option in ampd.OPTION_NAMES:
            button = builder.get_object('togglebutton-' + option)
            self.unit.unit_persistent.bind_property('protect-active', button, 'sensitive', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: not value)

        self.scale_time = builder.get_object('scale-time')
        label_time = builder.get_object('label-time')
        label_time_total = builder.get_object('label-time-total')
        self.volume_button = builder.get_object('volume-button')

        self.main = builder.get_object('main')
        self.add(self.main)

        self.headerbar = builder.get_object('headerbar')
        self.set_titlebar(self.headerbar)
        self.label_title = builder.get_object('label-title')
        self.label_subtitle = builder.get_object('label-subtitle')

        self.unit.unit_server.ampd_server_properties.bind_property('state', builder.get_object('button-play'), 'visible', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: value != 'play')
        self.unit.unit_server.ampd_server_properties.bind_property('state', builder.get_object('button-pause'), 'visible', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: value == 'play')
        self.unit.unit_server.ampd_server_properties.bind_property('state', self.scale_time, 'sensitive', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: value in {'play', 'pause'})
        self.unit.unit_server.ampd_server_properties.bind_property('volume', self.volume_button, 'value', GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)
        self.unit.unit_server.ampd_server_properties.bind_property('volume', self.volume_button, 'sensitive', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: value != -1)
        self.unit.unit_persistent.bind_property('protect-requested', builder.get_object('image-protected'), 'visible', GObject.BindingFlags.SYNC_CREATE)
        self.unit.unit_persistent.bind_property('protect-active', self.scale_time, 'sensitive', GObject.BindingFlags.INVERT_BOOLEAN | GObject.BindingFlags.SYNC_CREATE)
        label_time.bind_property('visible', label_time_total, 'visible', GObject.BindingFlags.SYNC_CREATE)
        self.unit.unit_server.ampd_server_properties.bind_property('bitrate', builder.get_object('label-bitrate'), 'label', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: ' [{kbps}kbps]'.format(kbps=value) if value else '')
        self.unit.unit_server.ampd_server_properties.bind_property('duration', self.scale_time.get_adjustment(), 'upper', GObject.BindingFlags.SYNC_CREATE)
        self.unit.unit_server.ampd_server_properties.bind_property('duration', self.scale_time.get_adjustment(), 'value', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: binding.get_source().elapsed)
        self.unit.unit_server.ampd_server_properties.bind_property('elapsed', self.scale_time, 'fill-level', GObject.BindingFlags.SYNC_CREATE)
        self.scale_time_binding = None
        self.scale_time.get_adjustment().bind_property('value', label_time, 'label', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: data.format_time(value + 0.5))
        self.scale_time.get_adjustment().bind_property('upper', label_time_total, 'label', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: ' / ' + data.format_time(value))
        self.scale_time.get_adjustment().bind_property('upper', label_time, 'visible', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: value != 0.0)
        self.set_scale_time_binding()

        self.scale_time.connect('notify::senstive', self.scale_time_notify_sensitive_cb)
        self.scale_time.connect('button-press-event', self.scale_time_button_press_event_cb)
        self.scale_time.connect('button-release-event', self.scale_time_button_release_event_cb)

        self.add_action(resource.Action('toggle-fullscreen', self.action_toggle_fullscreen_cb))
        self.add_action(resource.Action('volume-popup', self.action_volume_popup_cb))

        self.logging_handler = WindowLoggingHandeler(builder.get_object('box-info'), self.unit.config.message_timeout._get() * 1000)
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

    def notify_current_song_cb(self, *args):
        self.scale_time_break_interaction()
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
        self.label_title.set_label(window_title.format(artist=artist, title=title))

    def update_subtitle(self, *args):
        chunks = []
        if self.component:
            chunks.append(self.component.full_title)
        if self.unit.unit_server.server_label:
            chunks.append(self.unit.unit_server.server_label)
        self.label_subtitle.set_label(' / '.join(chunks))

    def do_configure_event(self, event):
        if not self.is_fullscreen:
            self.unit.config.width._set(event.width)
            self.unit.config.height._set(event.height)
            self.unit.config.maximized._set(self.is_maximized())
        Gtk.ApplicationWindow.do_configure_event(self, event)

    def scale_time_button_press_event_cb(self, scale_time, event):
        if event.button == 1 and event.type == Gdk.EventType.BUTTON_PRESS and self.scale_time_binding:
            self.scale_time_binding.unbind()
            self.scale_time_binding = None
        else:
            self.scale_time_break_interaction()

    def scale_time_button_release_event_cb(self, scale_time, event):
        if not self.scale_time_binding:
            if event.button == 1 and event.state & (Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK) == 0:
                self.unit.unit_server.ampd_server_properties.elapsed = self.scale_time.get_value()
                self.set_scale_time_binding()
            else:
                self.scale_time_break_interaction()

    def scale_time_break_interaction(self, *args):
        if not self.scale_time_binding:
            self.scale_time.set_sensitive(False)
            GLib.idle_add(lambda: self.scale_time.set_sensitive(True) or GLib.SOURCE_REMOVE)

    def scale_time_notify_sensitive_cb(self, *args):
        if not self.scale_time.get_sensitive():
            self.set_scale_time_binding()

    def set_scale_time_binding(self):
        if not self.scale_time_binding:
            self.scale_time_binding = self.unit.unit_server.ampd_server_properties.bind_property('elapsed', self.scale_time.get_adjustment(), 'value', GObject.BindingFlags.SYNC_CREATE)

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
    REQUIRED_UNITS = ['builder', 'persistent']

    def __init__(self, manager, name):
        super().__init__(manager, name)
        self.config.message_timeout._get(default=5)

    def new_window(self, app):
        return Window(app, self)
