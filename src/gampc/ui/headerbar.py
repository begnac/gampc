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
from gi.repository import GLib
from gi.repository import Gdk
from gi.repository import Gtk

from ..util.misc import format_time


class PlaybackButtons(Gtk.Box):
    playing = GObject.Property(type=bool, default=False)

    def __init__(self):
        super().__init__(visible=True)

        play_or_pause = Gtk.Button(visible=True, can_focus=False, action_name='app.play-or-pause')
        icon_play = Gtk.Image(visible=True, icon_name='media-playback-start-symbolic')
        icon_pause = Gtk.Image(visible=True, icon_name='media-playback-pause-symbolic')
        self.bind_property('playing', play_or_pause, 'image', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: icon_pause if value else icon_play)

        self.add(Gtk.Button(visible=True, can_focus=False, action_name='app.previous', image=Gtk.Image(visible=True, icon_name='media-skip-backward-symbolic')))
        self.add(play_or_pause)
        self.add(Gtk.Button(visible=True, can_focus=False, action_name='app.stop', image=Gtk.Image(visible=True, icon_name='media-playback-stop-symbolic')))
        self.add(Gtk.Button(visible=True, can_focus=False, action_name='app.next', image=Gtk.Image(visible=True, icon_name='media-skip-forward-symbolic')))


class OptionButtons(Gtk.Box):
    def __init__(self):
        super().__init__(visible=True)

        self.add(Gtk.ToggleButton(visible=True, can_focus=False, action_name='app.random', image=Gtk.Image(visible=True, icon_name='media-playlist-shuffle-symbolic')))
        self.add(Gtk.ToggleButton(visible=True, can_focus=False, action_name='app.repeat', image=Gtk.Image(visible=True, icon_name='media-playlist-repeat-symbolic')))
        self.add(Gtk.ToggleButton(visible=True, can_focus=False, action_name='app.single', image=Gtk.Image(visible=True, icon_name='zoom-original-symbolic')))
        # self.consume.set_image(Gtk.Image(visible=True, icon_name='media-skip-backward-symbolic'))


class TimeScale(Gtk.Box):
    duration = GObject.Property(type=float, default=0)
    elapsed = GObject.Property(type=float, default=0)

    def __init__(self):
        super().__init__(visible=True, orientation=Gtk.Orientation.HORIZONTAL)

        self.scale = Gtk.Scale(visible=True, can_focus=False, restrict_to_fill_level=False, show_fill_level=True, width_request=150, draw_value=False, has_origin=False)
        self.elapsed_label = Gtk.Label(visible=True)
        self.duration_label = Gtk.Label(visible=True)
        self.label_box = Gtk.Box()

        self.bind_property('duration', self.scale.get_adjustment(), 'upper', GObject.BindingFlags.SYNC_CREATE)
        self.bind_property('duration', self.scale.get_adjustment(), 'value', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: self.elapsed)
        self.bind_property('elapsed', self.scale, 'fill-level', GObject.BindingFlags.SYNC_CREATE)

        self.elapsed_binding = None
        self.set_elapsed_binding()

        self.scale.get_adjustment().bind_property('value', self.elapsed_label, 'label', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: format_time(value + 0.5))
        self.scale.get_adjustment().bind_property('upper', self.duration_label, 'label', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: ' / ' + format_time(value))
        self.scale.get_adjustment().bind_property('upper', self.label_box, 'visible', GObject.BindingFlags.SYNC_CREATE, lambda binding, value: value != 0.0)

        self.connect('notify::sensitive', self.notify_sensitive_cb)
        self.scale.connect('button-press-event', self.button_press_event_cb)
        self.scale.connect('button-release-event', self.button_release_event_cb)

        self.label_box.add(self.elapsed_label)
        self.label_box.add(self.duration_label)
        self.add(self.scale)
        self.add(self.label_box)

    def button_press_event_cb(self, scale, event):
        if event.button == 1 and event.type == Gdk.EventType.BUTTON_PRESS and self.elapsed_binding:
            self.elapsed_binding.unbind()
            self.elapsed_binding = None
        else:
            self.break_interaction()

    def button_release_event_cb(self, scale, event):
        if not self.elapsed_binding:
            if event.button == 1 and event.state & (Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK) == 0:
                self.elapsed = self.scale.get_value()
                self.set_elapsed_binding()
            else:
                self.break_interaction()

    def break_interaction(self, *args):
        if not self.elapsed_binding and self.get_sensitive():
            self.set_sensitive(False)
            GLib.idle_add(lambda: self.set_sensitive(True) or GLib.SOURCE_REMOVE)

    def set_elapsed_binding(self):
        if not self.elapsed_binding:
            self.elapsed_binding = self.bind_property('elapsed', self.scale.get_adjustment(), 'value', GObject.BindingFlags.SYNC_CREATE)

    def notify_sensitive_cb(self, *args):
        if not self.get_sensitive():
            self.set_elapsed_binding()


class HeaderBar(Gtk.HeaderBar):
    def __init__(self):
        super().__init__(visible=True, show_close_button=True)

        self.volume_button = Gtk.VolumeButton(visible=True, can_focus=False, orientation=Gtk.Orientation.VERTICAL)
        self.volume_button.get_adjustment().set_upper(100)
        self.volume_button.get_adjustment().set_step_increment(1)
        self.volume_button.get_adjustment().set_page_increment(5)
        self.playback_buttons = PlaybackButtons()
        self.time_scale = TimeScale()
        self.bitrate_label = Gtk.Label(visible=True)
        for widget in self.volume_button, self.playback_buttons, self.time_scale, self.bitrate_label:
            self.pack_start(widget)

        self.option_buttons = OptionButtons()
        self.protected_image = Gtk.Image(icon_name='security-high-symbolic', tooltip_text=_("Protected mode"))
        for widget in self.option_buttons, self.protected_image:
            self.pack_end(widget)
