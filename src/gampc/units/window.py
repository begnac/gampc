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

from .. import util
from ..util import resource
from ..util import unit
from ..util.logger import logger
from ..ui import headerbar
from ..ui import logging

from .. import __application__


class Window(Gtk.ApplicationWindow):
    def __init__(self, unit, **kwargs):
        super().__init__(show_menubar=True, **kwargs)

        # self.shortcut_accregator = shortcut.ShortcutAggregator(['win.accel'], _("Global shortcuts"))
        # unit.manager.add_aggregator(self.shortcut_accregator)
        # self.add_controller(self.shortcut_accregator.controller)

        controller = util.action.ShortcutController(self, is_global=True)
        for family in unit.action_info_families.values():
            family.add_to_shortcut_controller(controller)

        self.unit = unit
        self.component = None

        self.default_width = self.unit.config.width._get(default=1000)
        self.default_height = self.unit.config.height._get(default=600)
        self.set_default_size(self.default_width, self.default_height)
        self.connect('notify::default-width', self.notify_default_size_cb)
        self.connect('notify::default-height', self.notify_default_size_cb)

        self.unit.unit_server.connect('notify::current-song', self.notify_current_song_cb)
        self.unit.unit_server.ampd_server_properties.connect('notify::state', self.update_title)
        self.unit.unit_server.connect('notify::server-label', self.update_subtitle)

        self.main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(self.main)

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

        self.logging_handler = logging.Handeler(self.unit.config.message_timeout._get() * 1000)
        logger.addHandler(self.logging_handler)
        self.main.append(self.logging_handler.box)

        self.update_title()
        self.update_subtitle()

    def __del__(self):
        logger.debug("Deleting {}".format(self))

    def shutdown(self):
        logger.debug("Destroying window: {}".format(self))
        self.change_component(None)
        logger.removeHandler(self.logging_handler)
        self.logging_handler.shutdown()
        self.remove_action('toggle-fullscreen')
        self.remove_action('volume-popup')
        self.unit.unit_server.disconnect_by_func(self.update_subtitle)
        self.unit.unit_server.ampd_server_properties.disconnect_by_func(self.set_time_scale_sensitive)
        self.unit.unit_server.ampd_server_properties.disconnect_by_func(self.update_title)
        self.unit.unit_server.disconnect_by_func(self.notify_current_song_cb)
        self.unit.unit_persistent.disconnect_by_func(self.set_time_scale_sensitive)

    def change_component(self, component):
        if self.component is not None:
            self.component.disconnect_by_func(self.update_subtitle)
            self.component.disconnect_by_func(self.update_title)
            self.main.remove(self.component.widget)
            self.component.remove_action_groups(self)
            for cb in self.component.window_signals.values():
                self.disconnect_by_func(cb)
        self.component = component
        if self.component is not None:
            for name, cb in self.component.window_signals.items():
                self.connect(name, cb)
            self.component.insert_action_groups(self)
            self.main.prepend(self.component.widget)
            if self.component.focus_widget is not None:
                self.component.focus_widget.grab_focus()
            else:
                self.component.widget.grab_focus()
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
            window_title = __application__.upper()
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

    def action_toggle_fullscreen_cb(self, *args):
        if self.is_fullscreen():
            self.unfullscreen()
        else:
            self.fullscreen()

    @staticmethod
    def notify_default_size_cb(self, param):
        if not self.is_fullscreen():
            width, height = self.get_default_size()
            self.unit.config.width._set(width)
            self.unit.config.height._set(height)

    def action_volume_popup_cb(self, action, parameter):
        if self.volume_button.is_sensitive() and not self.volume_button.get_popup().get_mapped():
            self.volume_button.emit('popup')
        else:
            self.volume_button.emit('popdown')


@unit.require_units('persistent', 'component')
class __unit__(unit.UnitConfigMixin, unit.UnitServerMixin, unit.Unit):
    def __init__(self, manager, name):
        super().__init__(manager, name)
        self.config.message_timeout._get(default=5)

    def new_window(self, app):
        return Window(self, application=self.app)

    def generate_actions(self):
        yield util.action.ActionInfo('new-window', self.new_window_cb, _("New window"), ['<Control>n'])
        yield util.action.ActionInfo('close-window', self.close_window_cb, _("Close window"), ['<Control>w'])
        yield util.action.ActionInfo('quit', self.quit_cb, _("Quit"), ['<Control>q'])

        # yield util.action.ActionInfo('notify', self.task_hold_app(self.action_notify_cb))
        yield util.action.ActionInfo('component-start', self.component_start_cb, parameter_format='(sbb)')
        # yield util.action.ActionInfo('component-start-new-window', self.component_start_cb, parameter_format='sb')
        yield util.action.ActionInfo('component-stop', self.component_stop_cb)

    def new_window_cb(self, action, parameter):
        component = self.unit_component.get_component('current', False)
        self.display_component(component, True)

    def close_window_cb(self, action, parameter):
        self.app.get_active_window().destroy()

    @staticmethod
    def quit_cb(action, parameter):
        Gtk.Application.get_default().quit()

    def component_start_cb(self, action, parameter):
        name, new_window, new_instance = parameter.unpack()
        component = self.unit_component.get_component(name, new_instance)
        self.display_component(component, action.get_name().endswith('new-window'))

    def display_component(self, component, new_window):
        if new_window:
            window = self.new_window(self)
        else:
            window = component.get_window() or self.app.get_active_window() or self.new_window(self)
        if component.get_window() is None:
            window.change_component(component)
        window.present()

    def component_stop_cb(self, action, parameter):
        window = self.app.get_active_window()
        component = window.component
        if component:
            window.change_component(self.unit_component.get_free_component())
            self.unit_component.remove_component(component)
