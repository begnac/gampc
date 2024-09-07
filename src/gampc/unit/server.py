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

import asyncio
import ampd

from ..util import action
from ..util import unit
from ..util.logger import logger

from . import mixins


class __unit__(mixins.UnitConfigMixin, unit.Unit):
    server_label = GObject.Property(type=str, default='')
    server_profile = GObject.Property(type=str)

    def __init__(self, manager):
        super().__init__(manager)

        self.require('profiles')
        self.require('fields')

        self.ampd_client = ampd.ClientGLib()
        self.connect_clean(self.ampd_client, 'client-connected', self.client_connected_cb)
        self.connect_clean(self.ampd_client, 'client-disconnected', self.client_disconnected_cb)

        self.ampd = self.ampd_client.executor.sub_executor()

        self.ampd_server_properties = ampd.ServerPropertiesGLib(self.ampd_client.executor)
        self.connect_clean(self.ampd_server_properties, 'server-error', self.server_error_cb)
        self.connect_clean(self.ampd_server_properties, 'notify::updating-db', self.set_server_label)

        self.want_to_connect = False

        self.server_profile = self.config.server_profile._get(default=self.unit_profiles.LOCAL_HOST_NAME)
        self.server_profile_previous = self.config.server_profile_previous._get(default=self.server_profile)
        self.server_profile_backup = self.server_profile

        self.profile = self.unit_profiles.profile_from_repr(self.server_profile)
        self.set_server_label()

        self.connect_clean(self, 'notify::server-profile', self.notify_server_profile_cb)

    def cleanup(self):
        self.want_to_connect = False
        asyncio.get_event_loop().run_until_complete(self.ampd_client.close())
        del self.ampd_client
        del self.ampd_server_properties
        super().cleanup()

    def generate_database_actions(self):
        yield action.ActionInfo('update', self.update_cb, _("Update database"))

    def generate_connection_actions(self):
        yield action.ActionInfo('connect', self.ampd_connect, _("Connect"), ['<Alt><Shift>c'])
        yield action.ActionInfo('disconnect', self.ampd_disconnect, _("Disconnect"), ['<Alt><Shift>d'])
        yield action.ActionInfo('connect-to-previous', self.ampd_connect_to_previous, _("Connect to previous"), ['<Control><Alt>p'])
        yield action.PropertyActionInfo('server-profile', self)
        for name in ampd.OPTION_NAMES:
            yield action.PropertyActionInfo(name, self.ampd_server_properties, arg_format='i')

    def ampd_connect(self, *args):
        self.want_to_connect = True
        asyncio.create_task(self.ampd_client.connect_to_server(self.profile.address))
        self.set_server_label()

    def ampd_disconnect(self, *args):
        self.want_to_connect = False
        asyncio.create_task(self.ampd_client.disconnect_from_server())
        self.set_server_label()

    @ampd.task
    async def ampd_connect_to_previous(self, *args):
        self.server_profile = self.server_profile_previous

    @ampd.task
    async def update_cb(self, caller, *data):
        # if not self.ampd_server_properties.state:
        #     await self.ampd.idle(ampd.IDLE)
        await self.ampd.update()

    def client_connected_cb(self, client):
        logger.info(_("Connected to {address} [protocol version {protocol}]").format(address=self.profile.name, protocol=self.ampd.get_protocol_version()))
        self.set_server_label()

    def client_disconnected_cb(self, client, reason, message):
        if reason == ampd.Client.DISCONNECT_RECONNECT:
            return
        elif reason == ampd.Client.DISCONNECT_PASSWORD:
            logger.error(_("Invalid password"))
            return
        elif reason == ampd.Client.DISCONNECT_FAILED_CONNECT:
            logger.error(_("Connection failed: {message}").format(message=message or _("reason unknown")))
        else:
            logger.info(_("Disconnected"))
        if self.want_to_connect:
            self._reconnect()
        self.set_server_label()

    @ampd.task
    async def _reconnect(self):
        await asyncio.sleep(1)
        await self.ampd_client.connect_to_server(self.profile.address)

    def server_error_cb(self, client, error):
        logger.error(_("Server error: {error}").format(error=error))

    def set_server_label(self, *args):
        if not self.want_to_connect:
            self.server_label = _("Not connected")
        elif not self.ampd.get_is_connected():
            self.server_label = _("Connecting to {profile}").format(profile=self.profile.name)
        else:
            self.server_label = self.profile.name
            if self.ampd_server_properties.updating_db:
                self.server_label += " [{}]".format(_("database update"))

    @staticmethod
    def notify_server_profile_cb(self, param):
        self.profile = self.unit_profiles.profile_from_repr(self.server_profile)
        self.set_server_label()
        self.config.server_profile._set(self.server_profile)
        self.ampd_connect()
        if self.server_profile != self.server_profile_backup:
            self.config.server_profile_previous._set(self.server_profile_backup)
            self.server_profile_previous = self.server_profile_backup
            self.server_profile_backup = self.server_profile
