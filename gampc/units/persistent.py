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


class __unit__(unit.UnitMixinServer, unit.Unit):
    REQUIRED_UNITS = ['menubar']
    STICKER_PROPERTIES = ('protected', 'dark')

    protected = GObject.Property(type=bool, default=False)
    dark = GObject.Property(type=bool, default=False)

    def __init__(self, name, manager):
        super().__init__(name, manager)

        self.connect('notify::dark', self.notify_dark_cb)
        self.connect('notify::protected', self.notify_protected_cb)
        self.connect('notify', self.notify_sticker_cb)
        for option in ampd.OPTION_NAMES:
            self.unit_server.ampd_server_properties.connect('notify::' + option, self.notify_option_cb)

        self.unit_server.ampd_client.connect('client-connected', self.client_connected_cb)

        self.new_resource_provider('app.action').add_resources(
            resource.PropertyActionModel('protected', self),
            resource.PropertyActionModel('dark', self),
        )

        self.new_resource_provider('app.menu').add_resources(
            resource.UserAction('app.protected', _("Protected mode"), 'gampc/persistent', ['<Control><Alt>r']),
            resource.UserAction('app.dark', _("Dark interface"), 'gampc/persistent', ['<Control><Alt>d']),
        )

    def shutdown(self):
        self.disconnect_by_func(self.notify_sticker_cb)
        self.disconnect_by_func(self.notify_protected_cb)
        self.disconnect_by_func(self.notify_dark_cb)
        self.unit_server.ampd_client.disconnect_by_func(self.client_connected_cb)
        super().shutdown()

    def client_connected_cb(self, client):
        self.idle_sticker()

    @ampd.task
    async def idle_sticker(self):
        while True:
            self.read_sticker_properties()
            await self.ampd.idle(ampd.STICKER)

    @ampd.task
    async def read_sticker_properties(self):
        self.handler_block_by_func(self.notify_sticker_cb)
        try:
            stickers = await self.ampd.sticker_list('song', self.unit_server.SEPARATOR_FILE)
        except (ampd.errors.ReplyError, ampd.errors.ConnectionError):
            stickers = []
        pdict = dict(sticker.split('=', 1) for sticker in stickers)
        for key in self.STICKER_PROPERTIES:
            self.set_property(key, pdict.get(key) == 'True')
        self.handler_unblock_by_func(self.notify_sticker_cb)

    @staticmethod
    def notify_dark_cb(self, param):
        css = Gtk.CssProvider.get_named('Adwaita', 'dark' if self.dark else None)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    @staticmethod
    def notify_protected_cb(self, param):
        if self.protected:
            for option in ampd.OPTION_NAMES:
                self.unit_server.ampd_server_properties.set_property(option, False)

    @ampd.task
    async def notify_option_cb(self, properties, param):
        if self.protected:
            await getattr(self.ampd, param.name)(0)

    @staticmethod
    @ampd.task
    async def notify_sticker_cb(self, param):
        if param.name in self.STICKER_PROPERTIES:
            await self.ampd.sticker_set('song', self.unit_server.SEPARATOR_FILE, param.name, str(self.get_property(param.name)))
