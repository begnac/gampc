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

import ampd

from ..util import action
from ..util import unit
from ..util.logger import logger

from . import mixins


class __unit__(mixins.UnitServerMixin, unit.Unit):
    STICKER_PROPERTIES = ('protect-requested', 'dark')

    protect_requested = GObject.Property(type=bool, default=False)
    protect_active = GObject.Property(type=bool, default=False)
    dark = GObject.Property(type=bool, default=False)

    def __init__(self, manager):
        super().__init__(manager)

        self.require('database')

        self.connect_clean(self.unit_server.ampd_server_properties, 'notify::state', lambda obj, param: self.notify_protect_requested_cb(param))
        self.connect('notify::protect-requested', self.__class__.notify_protect_requested_cb)
        self.connect('notify', self.__class__.notify_sticker_cb)
        for option in ampd.OPTION_NAMES:
            self.unit_server.ampd_server_properties.connect('notify::' + option, self.notify_option_cb)

    def generate_actions(self):
        yield action.PropertyActionInfo('dark', self, _("Dark interface"), ['<Control><Alt>d'])
        yield action.PropertyActionInfo('protect-requested', self, _("Protected mode"), ['<Control><Alt>r'])

    def protect(self, action):
        self.bind_property('protect-active', action, 'enabled', GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.INVERT_BOOLEAN)

    def client_connected_cb(self, client):
        self.idle_sticker()
        self.idle_player()

    @ampd.task
    async def idle_sticker(self):
        while True:
            self.read_sticker_properties()
            await self.ampd.idle(ampd.STICKER)

    @ampd.task
    async def idle_player(self):
        while True:
            await self.ampd.idle(ampd.PLAYER)
            if self.protect_requested and (await self.ampd.status())['state'] == 'pause':
                await self.ampd.play()
                logger.info(_("Paused while protected.  Playing."))

    @ampd.task
    async def read_sticker_properties(self):
        self.handler_block_by_func(self.__class__.notify_sticker_cb)
        try:
            stickers = await self.ampd.sticker_list('song', self.unit_database.SEPARATOR_FILE)
        except (ampd.errors.ReplyError, ampd.errors.ConnectionError):
            stickers = []
        pdict = dict(sticker.split('=', 1) for sticker in stickers)
        for key in self.STICKER_PROPERTIES:
            self.set_property(key, pdict.get(key) == 'True')
        self.handler_unblock_by_func(self.__class__.notify_sticker_cb)

    def notify_protect_requested_cb(self, param):
        self.protect_active = self.protect_requested and self.unit_server.ampd_server_properties.state == 'play'
        if self.protect_requested:
            for option in ampd.OPTION_NAMES:
                self.unit_server.ampd_server_properties.set_property(option, False)

    @ampd.task
    async def notify_option_cb(self, properties, param):
        if self.protect_requested:
            await getattr(self.ampd, param.name)(0)

    @ampd.task
    async def notify_sticker_cb(self, param):
        if param.name in self.STICKER_PROPERTIES:
            await self.ampd.sticker_set('song', self.unit_database.SEPARATOR_FILE, param.name, str(self.get_property(param.name)))
