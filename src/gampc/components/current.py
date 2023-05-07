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
from gi.repository import GdkPixbuf
from gi.repository import Pango
from gi.repository import Gtk

import xdg
import time
import asyncio
import ampd

from . import component


class PixbufCache(dict):
    def __missing__(self, key):
        pixbuf = self.find_image(key)
        if pixbuf is not None:
            self[key] = pixbuf
        return pixbuf

    def find_image(self, key):
        for extension in ('.jpg', '.png', '.gif'):
            for name in xdg.BaseDirectory.load_data_paths('gampc', 'photos', key + extension):
                return GdkPixbuf.Pixbuf.new_from_file(name)

        for sep in (', ', ' y '):
            if sep in key:
                return self.find_images(key.split(sep))

        return None

    def find_images(self, names):
        pixbufs = [self[name] for name in names]
        if not all(pixbufs):
            return None
        width = height = 0
        for p in pixbufs:
            p.w = p.get_width()
            p.h = p.get_height()
            p.r = p.w / p.h
            height = max(height, 2 * p.h)
        for p in pixbufs:
            p.nw = height * p.r
            p.x = width
            width += p.nw
        pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, width, height)
        for p in pixbufs:
            p.composite(pixbuf, p.x, 0, p.nw, height, p.x, 0, height / p.h, height / p.h, GdkPixbuf.InterpType.BILINEAR, 255)
        return pixbuf


class Current(component.Component):
    size = GObject.Property(type=int)

    @staticmethod
    def make_label_image_box():
        label = Gtk.Label(visible=True, vexpand=True, ellipsize=Pango.EllipsizeMode.MIDDLE, lines=3, wrap=True)

        image = Gtk.Image(visible=True, vexpand=True)
        image_label = Gtk.Label(visible=True)

        box = Gtk.Box(visible=True, orientation=Gtk.Orientation.VERTICAL)
        box.add(label)
        box.add(image)
        box.add(image_label)

        return box, label, image, image_label

    def __init__(self, *args):
        super().__init__(*args)
        self.window_signals['check-resize'] = self.window_check_resize_cb

        self.pixbufs = PixbufCache()

        self.labels = {}
        self.images = {}
        self.image_labels = {}

        self.app_icon = Gtk.Image(visible=True, icon_name='face-cool-gampc')
        self.app_label = Gtk.Label(visible=True, label="GAMPC")
        self.app_label.set_attributes(Pango.AttrList.from_string('0 -1 font-desc "Sans Bold", 0 -1 scale 5'))

        self.welcome = Gtk.Box(vexpand=True, spacing=50)
        self.welcome.add(Gtk.Label(visible=True, hexpand=True))
        self.welcome.add(self.app_icon)
        self.welcome.add(self.app_label)
        self.welcome.add(Gtk.Label(visible=True, hexpand=True))

        artist_box, self.labels['Artist'], self.images['Artist'], self.image_labels['Artist'] = self.make_label_image_box()
        self.labels['Artist'].set_attributes(Pango.AttrList.from_string('0 -1 font-desc "Serif Bold", 0 -1 scale 2'))

        performer_box, self.labels['Performer'], self.images['Performer'], self.image_labels['Performer'] = self.make_label_image_box()
        self.labels['Performer'].set_attributes(Pango.AttrList.from_string('0 -1 font-desc "Sans", 0 -1 scale 2'))

        artist_performer_box = Gtk.Box(visible=True, homogeneous=True, spacing=50)
        artist_performer_box.add(artist_box)
        artist_performer_box.add(performer_box)

        self.labels['Title'] = title_label = Gtk.Label(visible=True, vexpand=True, ellipsize=Pango.EllipsizeMode.MIDDLE)
        title_label.set_attributes(Pango.AttrList.from_string('0 -1 font-desc "Sans Bold Italic", 0 -1 scale 3'))

        self.labels['Genre'] = genre_label = Gtk.Label(visible=True)
        self.labels['Date'] = date_label = Gtk.Label(visible=True)
        self.labels['Composer'] = composer_label = Gtk.Label(visible=True)
        data_box = Gtk.Box(visible=True, halign=Gtk.Align.CENTER, spacing=14)
        data_box.add(genre_label)
        data_box.add(Gtk.Label(visible=True, label="/"))
        data_box.add(date_label)
        data_box.add(Gtk.Label(visible=True, label="/"))
        data_box.add(composer_label)

        info_box = Gtk.Box(visible=True, orientation=Gtk.Orientation.VERTICAL)
        info_box.add(title_label)
        info_box.add(data_box)

        self.current = Gtk.Box(hexpand=True, orientation=Gtk.Orientation.VERTICAL, homogeneous=True)
        self.current.add(artist_performer_box)
        self.current.add(info_box)

        self.widget = self.main_box = Gtk.Box(visible=True, margin_bottom=20, margin_left=20, margin_right=20, margin_top=20)
        self.main_box.add(self.welcome)
        self.main_box.add(self.current)

        self.unit.unit_server.bind_property('current-song', self.welcome, 'visible', GObject.BindingFlags.SYNC_CREATE, lambda x, y: not y)
        self.unit.unit_server.bind_property('current-song', self.current, 'visible', GObject.BindingFlags.SYNC_CREATE, lambda x, y: bool(y))
        self.signal_handler_connect(self.unit.unit_server, 'notify::current-song', self.fader)
        self.fading = None

        self.width = 0
        self.css_provider = Gtk.CssProvider.new()
        self.widget.get_style_context().add_provider(self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.widget.connect('size-allocate', self.size_allocate_cb)
        self.bind_property('size', self.app_icon, 'pixel-size', GObject.BindingFlags(0), lambda x, y: y * 5)

        for field in self.labels.keys():
            label = self.labels[field]
            label.field = field
            image = self.images.get(field)
            if image:
                image_label = self.image_labels.get(field)
                if image_label:
                    label.bind_property('label', image_label, 'label', GObject.BindingFlags.SYNC_CREATE)
                    image.bind_property('visible', image_label, 'visible', GObject.BindingFlags.SYNC_CREATE)
                label.connect('notify::label', self.notify_label_cb, image)
                image.connect('size-allocate', self.image_size_allocate_cb)
            else:
                self.unit.unit_server.bind_property('current-song',
                                                    label, 'visible',
                                                    GObject.BindingFlags.SYNC_CREATE,
                                                    lambda x, y, z: z in y,
                                                    None, field)
            self.unit.unit_server.bind_property('current-song',
                                                label, 'label',
                                                GObject.BindingFlags.SYNC_CREATE,
                                                lambda x, y, z: self.set_size() or y.get(z, ''),
                                                None, field)

        self.widget.connect('map', self.__map_cb)

    def shutdown(self):
        if self.fading:
            self.fading.cancel()
            self.fading = None
        super().shutdown()

    def __map_cb(self, widget):
        self.width = 0
        self.set_size()

    def window_check_resize_cb(self, win):
        for image in self.images.values():
            image.clear()
            image.last_width = image.last_height = None

    def notify_label_cb(self, label, param, image):
        text = label.get_text()
        if not text or (label.field == 'Performer' and text == 'Instrumental'):
            label.get_parent().set_visible(False)
            return

        image.pixbuf = self.pixbufs[text]
        if image.pixbuf:
            image.last_width = image.last_height = None
            image.set_visible(True)
            label.set_visible(False)
        else:
            image.set_visible(False)
            label.set_visible(True)
        label.get_parent().set_visible(True)

    @ampd.task
    async def fader(self, *args):
        START = 30
        DURATION = 3
        INTERVAL = 0.05

        if self.fading:
            self.fading.cancel()
        task = self.fading = asyncio.current_task()
        try:
            if self.unit.unit_persistent.dark and self.unit.unit_server.current_song:
                self.current.set_opacity(0)
                await asyncio.sleep(START)
                t0 = t1 = time.time()
                while t1 < t0 + DURATION:
                    self.current.set_opacity((t1 - t0) / DURATION)
                    await asyncio.sleep(INTERVAL)
                    t1 = time.time()
            self.current.set_opacity(1)
        finally:
            if self.fading == task:
                self.fading = None

    def do_button_press_event(self, event):
        if event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS and event.button == 1:
            self.get_window().action_toggle_fullscreen_cb()

    def size_allocate_cb(self, widget, allocation):
        self.width = allocation.width
        self.set_size()

    def set_size(self):
        scale = 50.0
        song = self.unit.unit_server.current_song
        if song:
            scale += 3 * max(len(song.get('Artist', '')) - 20, len(song.get('Title', '')) - 20, 0)
        self.size = self.width / scale
        css = b'* { font-size: ' + str(self.size).encode() + b'px; }'
        self.css_provider.load_from_data(css)

    def image_size_allocate_cb(self, image, allocation):
        if self.width == 0 or (image.last_width == allocation.width and image.last_height == allocation.height):
            return
        image.last_width = allocation.width
        image.last_height = allocation.height
        ratio = image.pixbuf.get_height() / image.pixbuf.get_width()
        if allocation.width * ratio < allocation.height:
            allocation.height = allocation.width * ratio
        else:
            allocation.width = allocation.height / ratio
        pixbuf = image.pixbuf.scale_simple(allocation.width, allocation.height, GdkPixbuf.InterpType.BILINEAR)
        image.set_from_pixbuf(pixbuf)
