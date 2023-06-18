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


class Welcome(Gtk.Box):
    size = GObject.Property(type=int)

    def __init__(self):
        super().__init__(vexpand=True, spacing=50)

        self.app_icon = Gtk.Image(visible=True, icon_name='face-cool-gampc')
        self.bind_property('size', self.app_icon, 'pixel-size', GObject.BindingFlags(0), lambda x, y: y * 5)

        self.app_label = Gtk.Label(visible=True, label="GAMPC")
        self.app_label.set_attributes(Pango.AttrList.from_string('0 -1 font-desc "Sans Bold", 0 -1 scale 5'))

        self.add(Gtk.Label(visible=True, hexpand=True))
        self.add(self.app_icon)
        self.add(self.app_label)
        self.add(Gtk.Label(visible=True, hexpand=True))


class Person(Gtk.Box):
    def __init__(self, image_cache, condition=None):
        super().__init__(visible=True, orientation=Gtk.Orientation.VERTICAL)

        self.image_cache = image_cache
        self.condition = condition

        self.label = Gtk.Label(vexpand=True, ellipsize=Pango.EllipsizeMode.MIDDLE, wrap=True, lines=3)
        self.label.connect('notify::label', self.notify_label_cb)

        self.image = Gtk.Image(vexpand=True)
        self.image_label = Gtk.Label()

        self.image.connect('size-allocate', self.image_size_allocate_cb)

        self.add(self.label)
        self.add(self.image)
        self.add(self.image_label)

    def clear(self):
        self.image.clear()
        self.last_wh = None

    def notify_label_cb(self, label, param):
        self.clear()

        name = self.label.props.label
        if not name or (self.condition and not self.condition(name)):
            self.set_visible(False)
            return

        self.set_visible(True)

        self.pixbuf = self.image_cache[name]
        if self.pixbuf:
            self.label.set_visible(False)
            self.image.set_visible(True)
            self.image_label.set_visible(True)
            self.image_label.set_label(name)
        else:
            self.label.set_visible(True)
            self.image.set_visible(False)
            self.image_label.set_visible(False)

    def image_size_allocate_cb(self, image, allocation):
        new_wh = allocation.width, allocation.height
        if self.last_wh == new_wh:
            return
        self.last_wh = new_wh
        ratio = self.pixbuf.get_height() / self.pixbuf.get_width()
        if allocation.width * ratio < allocation.height:
            allocation.height = allocation.width * ratio
        else:
            allocation.width = allocation.height / ratio
        pixbuf = self.pixbuf.scale_simple(allocation.width, allocation.height, GdkPixbuf.InterpType.BILINEAR)
        image.set_from_pixbuf(pixbuf)


class Info(Gtk.Box):
    size = GObject.Property(type=int)

    def __init__(self):
        super().__init__(hexpand=True, orientation=Gtk.Orientation.VERTICAL, homogeneous=True)
        self.pixbufs = PixbufCache()

        self.artist = Person(self.pixbufs)
        self.artist.label.set_attributes(Pango.AttrList.from_string('0 -1 font-desc "Serif Bold", 0 -1 scale 2'))

        self.performer = Person(self.pixbufs, lambda name: name != 'Instrumental')
        self.performer.label.set_attributes(Pango.AttrList.from_string('0 -1 font-desc "Sans", 0 -1 scale 2'))

        artist_performer_box = Gtk.Box(visible=True, vexpand=True, homogeneous=True, spacing=50)
        artist_performer_box.add(self.artist)
        artist_performer_box.add(self.performer)

        self.title_label = Gtk.Label(visible=True, vexpand=True, wrap=True)
        self.title_label.set_attributes(Pango.AttrList.from_string('0 -1 font-desc "Sans Bold Italic", 0 -1 scale 3'))

        self.genre_label = Gtk.Label(visible=True)
        self.date_label = Gtk.Label(visible=True)
        self.composer_label = Gtk.Label(visible=True)
        data_box = Gtk.Box(visible=True, vexpand=True, halign=Gtk.Align.CENTER, spacing=14)
        data_box.add(self.genre_label)
        data_box.add(Gtk.Label(visible=True, label="/"))
        data_box.add(self.date_label)
        data_box.add(Gtk.Label(visible=True, label="/"))
        data_box.add(self.composer_label)

        info_box = Gtk.Box(visible=True, vexpand=True, orientation=Gtk.Orientation.VERTICAL)
        info_box.add(self.title_label)
        info_box.add(data_box)

        self.add(artist_performer_box)
        self.add(info_box)

    def clear(self):
        self.artist.clear()
        self.performer.clear()


class Current(component.Component):
    size = GObject.Property(type=int)

    def __init__(self, *args):
        super().__init__(*args)
        self.window_signals['check-resize'] = self.window_check_resize_cb

        self.labels = {}

        welcome = Welcome()
        self.info = Info()

        self.labels = (
            ('Artist', self.info.artist.label),
            ('Performer', self.info.performer.label),
            ('Title', self.info.title_label),
            ('Genre', self.info.genre_label),
            ('Date', self.info.date_label),
            ('Composer', self.info.composer_label),
        )

        self.widget = self.main_box = Gtk.Box(visible=True, margin_bottom=20, margin_left=20, margin_right=20, margin_top=20)
        self.main_box.add(welcome)
        self.main_box.add(self.info)

        self.unit.unit_server.bind_property('current-song', welcome, 'visible', GObject.BindingFlags.SYNC_CREATE, lambda x, y: not y)
        self.unit.unit_server.bind_property('current-song', self.info, 'visible', GObject.BindingFlags.SYNC_CREATE, lambda x, y: bool(y))
        self.signal_handler_connect(self.unit.unit_server, 'notify::current-song', self.notify_current_song_cb)
        self.fading = None

        self.width = 0
        self.css_provider = Gtk.CssProvider.new()
        self.widget.get_style_context().add_provider(self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.widget.connect('size-allocate', self.size_allocate_cb)
        self.bind_property('size', welcome, 'size')

        self.widget.connect('map', self.__map_cb)

    def shutdown(self):
        if self.fading:
            self.fading.cancel()
            self.fading = None
        super().shutdown()

    def __map_cb(self, widget):
        self.width = 0
        self.set_size()

    def notify_current_song_cb(self, server, param):
        for field, label in self.labels:
            label.set_label(server.current_song.get(field, ''))
        self.set_size()
        # self.fader()

    def window_check_resize_cb(self, win):
        self.info.clear()

    # @ampd.task
    # async def fader(self, *args):
    #     START = 30
    #     DURATION = 3
    #     INTERVAL = 0.05

    #     if self.fading:
    #         self.fading.cancel()
    #     task = self.fading = asyncio.current_task()
    #     try:
    #         if self.unit.unit_persistent.dark and self.unit.unit_server.current_song:
    #             self.info.set_opacity(0)
    #             await asyncio.sleep(START)
    #             t0 = t1 = time.time()
    #             while t1 < t0 + DURATION:
    #                 self.info.set_opacity((t1 - t0) / DURATION)
    #                 await asyncio.sleep(INTERVAL)
    #                 t1 = time.time()
    #         self.info.set_opacity(1)
    #     finally:
    #         if self.fading == task:
    #             self.fading = None

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
