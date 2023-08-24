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
from gi.repository import GdkPixbuf
from gi.repository import Pango
from gi.repository import Gtk

import xdg
# import time
# import asyncio
# import ampd

from ..util import unit
from ..components import component
from .. import __application__


class PixbufCache(dict):
    def __missing__(self, key):
        pixbuf = self.find_image(key)
        if pixbuf is not None:
            self[key] = pixbuf
        return pixbuf

    def find_image(self, key):
        for extension in ('.jpg', '.png', '.gif'):
            for name in xdg.BaseDirectory.load_data_paths(__application__, 'photos', key + extension):
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

        self.icon = Gtk.Image(icon_name='face-cool-gampc')
        self.bind_property('size', self.icon, 'pixel-size', GObject.BindingFlags(0), lambda x, y: y * 5)

        self.label = Gtk.Label(label=__application__.upper())
        self.label.set_attributes(Pango.AttrList.from_string('0 -1 font-desc "Sans Bold", 0 -1 scale 5'))

        self.append(Gtk.Label(hexpand=True))
        self.append(self.icon)
        self.append(self.label)
        self.append(Gtk.Label(hexpand=True))


class Person(Gtk.Box):
    def __init__(self, image_cache, condition=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.image_cache = image_cache
        self.condition = condition

        self.label = Gtk.Label(vexpand=True, ellipsize=Pango.EllipsizeMode.MIDDLE, wrap=True, lines=3)

        self.image = Gtk.Image(vexpand=True)
        self.image_label = Gtk.Label()

        self.append(self.label)
        self.append(self.image)
        self.append(self.image_label)

    def set_name(self, name):
        if not name or (self.condition and not self.condition(name)):
            self.set_visible(False)
            return

        self.image.clear()
        self.set_visible(True)

        self.pixbuf = self.image_cache[name]
        if self.pixbuf:
            self.label.set_visible(False)
            self.image.set_visible(True)
            self.image_label.set_visible(True)
            self.image_label.set_label(name)
            self.image.set_from_pixbuf(self.pixbuf)
        else:
            self.label.set_label(name)
            self.label.set_visible(True)
            self.image.set_visible(False)
            self.image_label.set_visible(False)


class Info(Gtk.Box):
    size = GObject.Property(type=int)

    def __init__(self):
        super().__init__(hexpand=True, orientation=Gtk.Orientation.VERTICAL, homogeneous=True)
        self.pixbufs = PixbufCache()

        self.artist = Person(self.pixbufs)
        self.artist.label.set_attributes(Pango.AttrList.from_string('0 -1 font-desc "Serif Bold", 0 -1 scale 2'))

        self.performer = Person(self.pixbufs, lambda name: name != 'Instrumental')
        self.performer.label.set_attributes(Pango.AttrList.from_string('0 -1 font-desc "Sans", 0 -1 scale 2'))

        artist_performer_box = Gtk.Box(vexpand=True, homogeneous=True, spacing=50)
        artist_performer_box.append(self.artist)
        artist_performer_box.append(self.performer)

        self.title_label = Gtk.Label(vexpand=True, wrap=True)
        self.title_label.set_attributes(Pango.AttrList.from_string('0 -1 font-desc "Sans Bold Italic", 0 -1 scale 3'))

        self.genre_label = Gtk.Label()
        self.date_label = Gtk.Label()
        self.composer_label = Gtk.Label()
        data_box = Gtk.Box(vexpand=True, halign=Gtk.Align.CENTER, spacing=14)
        data_box.append(self.genre_label)
        data_box.append(Gtk.Label(label="/"))
        data_box.append(self.date_label)
        data_box.append(Gtk.Label(label="/"))
        data_box.append(self.composer_label)

        info_box = Gtk.Box(vexpand=True, orientation=Gtk.Orientation.VERTICAL)
        info_box.append(self.title_label)
        info_box.append(data_box)

        self.append(artist_performer_box)
        self.append(info_box)


class MyBoxLayout(Gtk.BoxLayout):
    size = GObject.Property(type=int)

    def do_allocate(self, box, width, height, baseline):
        self.size = width + height
        return Gtk.BoxLayout.do_allocate(self, box, width, height, baseline)


class Current(component.Component):
    size = GObject.Property(type=int)

    def __init__(self, *args):
        super().__init__(*args)

        welcome = Welcome()
        self.info = Info()

        self.labels = (
            ('Title', self.info.title_label),
            ('Genre', self.info.genre_label),
            ('Date', self.info.date_label),
            ('Composer', self.info.composer_label),
        )

        self.layout = MyBoxLayout()
        self.layout.connect('notify::size', self.notify_size_cb)
        self.widget = self.main_box = Gtk.Box(margin_bottom=20, margin_start=20, margin_end=20, margin_top=20, layout_manager=self.layout)
        self.main_box.append(welcome)
        self.main_box.append(self.info)

        self.unit.unit_server.bind_property('current-song', welcome, 'visible', GObject.BindingFlags.SYNC_CREATE, lambda x, y: not y)
        self.unit.unit_server.bind_property('current-song', self.info, 'visible', GObject.BindingFlags.SYNC_CREATE, lambda x, y: bool(y))
        self.signal_handler_connect(self.unit.unit_server, 'notify::current-song', self.notify_current_song_cb)
        # self.fading = None

        self.css_provider = Gtk.CssProvider()
        self.widget.get_style_context().add_provider(self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.bind_property('size', welcome, 'size')

    def shutdown(self):
        # if self.fading:
        #     self.fading.cancel()
        #     self.fading = None
        self.layout.disconnect_by_func(self.notify_size_cb)
        super().shutdown()

    def notify_current_song_cb(self, server, param):
        self.info.artist.set_name(server.current_song.get('Artist', ''))
        self.info.performer.set_name(server.current_song.get('Performer', ''))
        for field, label in self.labels:
            label.set_label(server.current_song.get(field, ''))
        self.set_size()
        # self.fader()

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

    def set_size(self):
        scale = 100.0
        song = self.unit.unit_server.current_song
        if song:
            scale += 3 * max(len(song.get('Artist', '')) - 20, len(song.get('Title', '')) - 20, 0)
        self.size = self.layout.size / scale
        css = f'* {{ font-size: {self.size}px; }}'
        self.css_provider.load_from_data(css, -1)

    def notify_size_cb(self, layout, param):
        self.set_size()


class __unit__(component.UnitComponentMixin, unit.Unit):
    title = _("Current Song")
    key = '0'

    REQUIRED_UNITS = ['persistent']
    COMPONENT_CLASS = Current
