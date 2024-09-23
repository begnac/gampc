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
from gi.repository import GLib
from gi.repository import Gdk
from gi.repository import Gtk

from ..util import misc


class PlaybackButtons(Gtk.Box):
    playing = GObject.Property(type=bool, default=False)

    def __init__(self):
        super().__init__()

        play_or_pause = Gtk.Button(action_name='app.play-or-pause')
        self.bind_property('playing', play_or_pause, 'icon-name', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: 'media-playback-pause-symbolic' if value else 'media-playback-start-symbolic')

        self.append(Gtk.Button(action_name='app.previous', icon_name='media-skip-backward-symbolic'))
        self.append(play_or_pause)
        self.append(Gtk.Button(action_name='app.stop', icon_name='media-playback-stop-symbolic'))
        self.append(Gtk.Button(action_name='app.next', icon_name='media-skip-forward-symbolic'))


class OptionButtons(Gtk.Box):
    def __init__(self):
        super().__init__()

        self.append(Gtk.ToggleButton(action_name='app.random', icon_name='media-playlist-shuffle-symbolic'))
        self.append(Gtk.ToggleButton(action_name='app.repeat', icon_name='media-playlist-repeat-symbolic'))
        # self.append(Gtk.ToggleButton(action_name='app.consume', icon_name='media-skip-backward-symbolic'))
        self.append(Gtk.ToggleButton(action_name='app.single', icon_name='zoom-original-symbolic'))


class TimeScale(Gtk.Box):
    duration = GObject.Property(type=float, default=0)
    elapsed = GObject.Property(type=float, default=0)

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)

        scale = self.scale = Gtk.Scale(restrict_to_fill_level=False, show_fill_level=True, width_request=150, draw_value=False, has_origin=False)
        self.elapsed_label = Gtk.Label()
        self.duration_label = Gtk.Label()
        self.label_box = Gtk.Box()

        self.bind_property('elapsed', self.scale, 'fill-level', GObject.BindingFlags.SYNC_CREATE)
        self.bind_property('duration', self.scale.get_adjustment(), 'upper', GObject.BindingFlags.SYNC_CREATE)
        self.bind_property('duration', self.scale.get_adjustment(), 'value', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: scale.get_fill_level())

        self.elapsed_binding = None
        self.set_elapsed_binding()

        self.scale.get_adjustment().bind_property('value', self.elapsed_label, 'label', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: misc.format_time(value + 0.5))
        self.scale.get_adjustment().bind_property('upper', self.duration_label, 'label', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: ' / ' + misc.format_time(value))
        self.scale.get_adjustment().bind_property('upper', self.label_box, 'visible', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: value != 0.0)

        self.connect('notify::sensitive', self.notify_sensitive_cb)
        for controller in self.scale.observe_controllers():
            if isinstance(controller, Gtk.GestureClick):
                self.scale_gesture_click = controller
                break
        else:
            raise RuntimeError

        self.label_box.append(self.elapsed_label)
        self.label_box.append(self.duration_label)
        self.append(self.scale)
        self.append(self.label_box)

        self.connect('realize', self.map_cb)
        self.connect('unrealize', self.unmap_cb)

    @staticmethod
    def map_cb(self):
        self.scale_gesture_click.connect('pressed', self.scale_pressed_cb)
        self.scale_gesture_click.connect('released', self.scale_released_cb)
        self.scale_gesture_click.connect('cancel', self.scale_cancel_cb)

    @staticmethod
    def unmap_cb(self):
        self.scale_gesture_click.disconnect_by_func(self.scale_pressed_cb)
        self.scale_gesture_click.disconnect_by_func(self.scale_released_cb)
        self.scale_gesture_click.disconnect_by_func(self.scale_cancel_cb)

    def scale_pressed_cb(self, controller, n_pressed, x, y):
        if controller.get_current_button() == 1 and n_pressed == 1 and self.elapsed_binding:
            self.elapsed_binding.unbind()
            self.elapsed_binding = None
        else:
            self.break_interaction()

    def scale_released_cb(self, controller, n_pressed, x, y):
        if not self.elapsed_binding:
            if controller.get_current_button() == 1 and misc.get_modifier_state() & (Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK) == 0:
                self.elapsed = self.scale.get_value()
                self.set_elapsed_binding()
            else:
                self.break_interaction()

    def scale_cancel_cb(self, controller, sequence):
        if not self.elapsed_binding:
            self.break_interaction()

    def break_interaction(self, *args):
        if not self.elapsed_binding and self.get_sensitive():
            self.set_sensitive(False)
            GLib.idle_add(self.set_sensitive, True)

    def set_elapsed_binding(self):
        if not self.elapsed_binding:
            self.elapsed_binding = self.bind_property('elapsed', self.scale.get_adjustment(), 'value', GObject.BindingFlags.SYNC_CREATE)

    @staticmethod
    def notify_sensitive_cb(self, param):
        if not self.get_sensitive():
            self.set_elapsed_binding()


class HeaderBar(Gtk.HeaderBar):
    def __init__(self, menu):
        self.title = Gtk.Label(css_classes=['title'])
        self.subtitle = Gtk.Label(css_classes=['subtitle'])
        self.titlebox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        self.titlebox.append(self.title)
        self.titlebox.append(self.subtitle)

        super().__init__(title_widget=self.titlebox)

        self.volume_button = Gtk.VolumeButton(orientation=Gtk.Orientation.VERTICAL)
        self.volume_button.get_adjustment().set_upper(100)
        self.volume_button.get_adjustment().set_step_increment(1)
        self.volume_button.get_adjustment().set_page_increment(5)
        self.playback_buttons = PlaybackButtons()
        self.time_scale = TimeScale()
        self.bitrate_label = Gtk.Label()
        for widget in self.volume_button, self.playback_buttons, self.time_scale, self.bitrate_label:
            self.pack_start(widget)

        self.menu_button = Gtk.MenuButton(icon_name='open-menu', menu_model=menu, primary=True)
        self.option_buttons = OptionButtons()
        self.protected_image = Gtk.Image(icon_name='security-high-symbolic', tooltip_text=_("Protected mode"))
        for widget in self.menu_button, self.option_buttons, self.protected_image:
            self.pack_end(widget)

    def set_title(self, title):
        self.title.set_label(title)

    def set_subtitle(self, subtitle):
        self.subtitle.set_label(subtitle)
