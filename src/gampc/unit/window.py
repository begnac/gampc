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
from gi.repository import Gtk

from ..util import action
from ..util import cleanup
from ..util import unit
from ..util.logger import logger

from ..ui import headerbar
from ..ui import logging

from .. import __application__

from . import mixins


class Window(cleanup.CleanupSignalMixin, Gtk.ApplicationWindow):
    def __init__(self, unit, **kwargs):
        super().__init__(**kwargs)

        self.action_info_families = list(unit.unit_menu.action_info_families)
        for family in self.action_info_families:
            self.add_controller(family.get_shortcut_controller())

        self.unit = unit
        self.component = None

        self.default_width = self.unit.config.width._get(default=1000)
        self.default_height = self.unit.config.height._get(default=600)
        self.set_default_size(self.default_width, self.default_height)
        self.connect('notify::default-width', self.__class__.notify_default_size_cb)
        self.connect('notify::default-height', self.__class__.notify_default_size_cb)

        self.connect_clean(self.unit.unit_server.ampd_server_properties, 'notify::current-song', self.notify_current_song_cb)
        self.connect_clean(self.unit.unit_server.ampd_server_properties, 'notify::state', self.update_title)
        self.connect_clean(self.unit.unit_server, 'notify::server-label', self.update_title)

        self.main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(self.main)

        self.headerbar = headerbar.HeaderBar()
        self.set_titlebar(self.headerbar)

        self.menubar = Gtk.PopoverMenuBar(menu_model=unit.unit_menu.menu)
        self.bind_property('fullscreened', self.menubar, 'visible', GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.INVERT_BOOLEAN)
        for child in self.menubar.observe_children():
            for controller in child.observe_controllers():
                if isinstance(controller, Gtk.EventControllerMotion):
                    enter_id = GObject.signal_lookup('enter', Gtk.EventControllerMotion)
                    GObject.signal_handlers_disconnect_matched(controller, GObject.SignalMatchType.ID, enter_id, 0)
        self.main.append(self.menubar)

        self.unit.unit_persistent.bind_property('protect-active', self.headerbar.option_buttons, 'sensitive', GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.INVERT_BOOLEAN)

        self.unit.unit_server.ampd_server_properties.bind_property('state', self.headerbar.playback_buttons, 'playing', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: value == 'play')
        self.unit.unit_server.ampd_server_properties.bind_property('volume', self.headerbar.volume_button, 'value', GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)
        self.unit.unit_server.ampd_server_properties.bind_property('volume', self.headerbar.volume_button, 'sensitive', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: value != -1)
        self.unit.unit_persistent.bind_property('protect-requested', self.headerbar.protected_image, 'visible', GObject.BindingFlags.SYNC_CREATE)
        self.unit.unit_server.ampd_server_properties.bind_property('bitrate', self.headerbar.bitrate_label, 'label', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: ' [{kbps}kbps]'.format(kbps=value) if value else '')

        self.unit.unit_server.ampd_server_properties.bind_property('duration', self.headerbar.time_scale, 'duration', GObject.BindingFlags.SYNC_CREATE)
        self.unit.unit_server.ampd_server_properties.bind_property('elapsed', self.headerbar.time_scale, 'elapsed', GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)

        self.connect_clean(self.unit.unit_server.ampd_server_properties, 'notify::state', self.set_time_scale_sensitive)
        self.connect_clean(self.unit.unit_persistent, 'notify::protect-active', self.set_time_scale_sensitive)

        self.logging_handler = logging.Handler(self.unit.config.message_timeout._get() * 1000)
        logger.addHandler(self.logging_handler)
        self.main.append(self.logging_handler.box)

        self.update_title()

    def cleanup(self):
        self.change_component(None)
        logger.removeHandler(self.logging_handler)
        self.logging_handler.cleanup()
        super().cleanup()

    def change_component(self, component):
        if self.component is not None:
            self.main.remove(self.component)
            self.set_subtitle()
        self.component = component
        if self.component is not None:
            self.main.insert_child_after(self.component, self.menubar)
            self.component.grab_focus()

    def set_time_scale_sensitive(self, *args):
        if self.unit.unit_persistent.protect_active or self.unit.unit_server.ampd_server_properties.state not in ('play', 'pause'):
            self.headerbar.time_scale.set_sensitive(False)
        else:
            self.headerbar.time_scale.set_sensitive(True)

    def notify_current_song_cb(self, *args):
        self.headerbar.time_scale.break_interaction()
        self.update_title()

    def update_title(self, *args):
        if self.unit.unit_server.ampd_server_properties.state in ('play', 'pause'):
            song = self.unit.unit_server.ampd_server_properties.current_song
            title = song.get('Title') or song.get('Name') or _("Unknown song")
            if 'Artist' in song:
                title = f"{title} / {song['Artist']}"
            if self.unit.unit_server.ampd_server_properties.state == 'pause':
                title = _("{title} (paused)").format(title=title)
        else:
            title = __application__.upper()
        server = self.unit.unit_server.server_label.rsplit('@', 1)[-1].strip()
        self.headerbar.set_title(f"{title} @ {server}")

    def notify_default_size_cb(self, param):
        if not self.is_fullscreen():
            width, height = self.get_default_size()
            self.unit.config.width._set(width)
            self.unit.config.height._set(height)

    def set_subtitle(self, subtitle=""):
        self.headerbar.subtitle.set_label(subtitle)


class __unit__(mixins.UnitConfigMixin, mixins.UnitServerMixin, unit.Unit):
    def __init__(self, manager):
        super().__init__(manager)
        self.require('menu')
        self.require('persistent')
        self.require('component')
        self.config.message_timeout._get(default=1)

        self.unit_menu.load_family(self.generate_actions(), _("Window"), Gtk.Application.get_default(), self.unit_menu.menu_window_section, True)

    def generate_actions(self):
        yield action.ActionInfo('new-window', self.new_window_cb, _("New window"), ['<Control>n'])
        yield action.ActionInfo('close-window', self.close_window_cb, _("Close window"), ['<Control>w'])
        # yield action.ActionInfo('toggle-fullscreen', self.action_toggle_fullscreen_cb, _("Fullscreen window"), ['<Alt>f'])
        # yield action.ActionInfo('notify', self.task_hold_app(self.action_notify_cb))

    def new_window(self, name='current'):
        window = Window(self, application=Gtk.Application.get_default())
        component = self.unit_component.get_component(name, False)
        if component is not None and component.get_root() is None:
            window.change_component(component)
        window.present()

    def new_window_cb(self, action, parameter):
        self.new_window()

    def close_window_cb(self, action, parameter):
        Gtk.Application.get_default().get_active_window().destroy()

    # def action_toggle_fullscreen_cb(self, action, parameter):
    #     window = self.app.get_active_window()
    #     if window.is_fullscreen():
    #         window.unfullscreen()
    #     else:
    #         window.fullscreen()
