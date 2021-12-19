# coding: utf-8
#
# Graphical Asynchronous Music Player Client
#
# Copyright (C) 2015 Itaï BEN YAACOV
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

import asyncio
import ampd

from gampc.util import resource
from gampc.util import unit
from gampc.util.logger import logger


class ServerOption(GObject.Object):
    value = GObject.Property(type=bool, default=False)

    def __init__(self):
        GObject.Object.__init__(self)


class __unit__(unit.UnitWithConfig):
    REQUIRED_UNITS = ['menubar', 'profiles']

    SEPARATOR_FILE = 'separator.mp3'

    server_label = GObject.Property(type=str, default='')
    server_profile = GObject.Property(type=str)
    server_partition = GObject.Property(default=None)
    server_profile_desired = GObject.Property(type=str)  # 'profile' or 'profile,partition'

    current_song = GObject.Property()  # 'profile' or 'profile,partition'

    def __init__(self, name, manager):
        super().__init__(name, manager)
        self.ampd_client = ampd.ClientGLib()
        self.ampd_client.connect('client-connected', self.client_connected_cb)
        self.ampd_client.connect('client-disconnected', self.client_disconnected_cb)

        self.ampd = self.ampd_client.executor.sub_executor()

        self.ampd_server_properties = ampd.ServerPropertiesGLib(self.ampd_client.executor)
        self.ampd_server_properties.bind_property('current-song', self, 'current-song', GObject.BindingFlags.SYNC_CREATE)
        self.ampd_server_properties.connect('server-error', self.server_error_cb)
        self.ampd_server_properties.connect('notify::updating-db', self.set_server_label)
        self.server_options = {name: ServerOption() for name in ampd.OPTION_NAMES}
        for name in ampd.OPTION_NAMES:
            self.ampd_server_properties.bind_property(name, self.server_options[name], 'value', GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)

        self.host = self.port = None
        self.want_to_connect = False

        self.server_profile_desired = self.config.server.access('profile-desired', self.unit_profiles.LOCAL_HOST)
        self.server_profile_previous = self.config.access('server-profile-previous', self.server_profile_desired)
        self.server_profile_backup = self.server_profile_desired

        self.connect('notify::server-profile', self.notify_server_profile_cb)
        self.connect('notify::server-partition', self.notify_server_partition_cb)
        self.connect('notify::server-profile-desired', self.notify_server_profile_desired_cb)

        self.unit_profiles.connect('notify::profiles', self.notify_profiles_cb)

        self.separator_song = {'file': self.SEPARATOR_FILE}

        self.new_resource_provider('app.action').add_resources(
            resource.PropertyActionModel('server-profile-desired', self),
            resource.ActionModel('connect', self.ampd_connect),
            resource.ActionModel('disconnect', self.ampd_disconnect),
            resource.ActionModel('connect-to-previous', self.ampd_connect_to_previous),
            resource.ActionModel('update', self.update_cb),
            *(resource.PropertyActionModel(name, self.server_options[name], property_name='value') for name in ampd.OPTION_NAMES)
        )

        self.new_resource_provider('app.menu').add_resources(
            resource.MenuPath('server/server/actions'),
            resource.MenuPath('server/server/options'),
            resource.MenuPath('server/server/partition'),
            resource.MenuPath('server/server/connection'),
        )

        self.new_resource_provider('app.user-action').add_resources(
            resource.UserAction('app.update', _("Update database"), 'server/server/actions'),
            resource.UserAction('app.random', _("Random mode"), 'server/server/options'),
            resource.UserAction('app.repeat', _("Repeat mode"), 'server/server/options'),
            resource.UserAction('app.consume', _("Consume mode"), 'server/server/options'),
            resource.UserAction('app.single', _("Single mode"), 'server/server/options'),
            resource.UserAction('app.connect', _("Connect"), 'server/server/connection', ['<Alt><Shift>c']),
            resource.UserAction('app.disconnect', _("Disconnect"), 'server/server/connection', ['<Alt><Shift>d']),
            resource.UserAction('app.connect-to-previous', _("Connect to previous"), 'server/server/connection', ['<Control><Alt>p']),
        )

    def shutdown(self):
        self.want_to_connect = False
        asyncio.get_event_loop().run_without_glib_until_complete(self.ampd_client.close())
        self.disconnect_by_func(self.notify_server_profile_desired_cb)
        self.disconnect_by_func(self.notify_server_partition_cb)
        self.disconnect_by_func(self.notify_server_profile_cb)
        self.unit_profiles.disconnect_by_func(self.notify_profiles_cb)
        self.ampd_client.disconnect_by_func(self.client_disconnected_cb)
        self.ampd_client.disconnect_by_func(self.client_connected_cb)
        self.ampd_server_properties.disconnect_by_func(self.set_server_label)
        self.ampd_server_properties.disconnect_by_func(self.server_error_cb)
        del self.ampd_client
        del self.ampd_server_properties
        super().shutdown()

    def ampd_connect(self, *args):
        self.server_partition = None
        self.want_to_connect = True
        self.server_profile = self.server_profile_desired.split(',', 1)[0]
        if self.server_profile not in self.unit_profiles.profiles:
            self.host = self.port = None
            raise RuntimeError("Profile {profile} not found".format(profile=self.server_profile))
        profile = self.unit_profiles.profiles[self.server_profile]
        self.host = profile['host']
        self.port = profile['port']
        asyncio.ensure_future(self.ampd_client.connect_to_server(self.host, self.port))
        self.set_server_label()

    def ampd_disconnect(self, *args):
        self.want_to_connect = False
        asyncio.ensure_future(self.ampd_client.disconnect_from_server())
        self.server_partition = None
        self.set_server_label()

    @ampd.task
    async def ampd_connect_to_previous(self, *args):
        self.server_profile_desired = self.server_profile_previous

    @ampd.task
    async def update_cb(self, caller, *data):
        # if not self.ampd_server_properties.state:
        #     await self.ampd.idle(ampd.IDLE)
        await self.ampd.update()

    def client_connected_cb(self, client):
        logger.info(_("Connected to {profile} [protocol version {protocol}]").format(profile=self.server_profile, protocol=self.ampd.get_protocol_version()))
        self._update_server_partition()
        self.idle_database()

    @ampd.task
    async def _update_server_partition(self):
        if ',' in self.server_profile_desired:
            partition = self.server_profile_desired.split(',', 1)[1]
            await self.ampd.partition(partition)
            self.server_partition = partition
        else:
            self.server_partition = (await self.ampd.status()).get('partition')

    def client_disconnected_cb(self, client, reason, message):
        self.separator_song.clear()
        self.separator_song['file'] = self.SEPARATOR_FILE
        if reason == ampd.Client.DISCONNECT_RECONNECT:
            return
        elif reason == ampd.Client.DISCONNECT_PASSWORD:
            logger.error(_("Invalid password for {}").format(self.server_profile))
            return
        elif reason == ampd.Client.DISCONNECT_FAILED_CONNECT:
            logger.error(_("Connection to {} failed: {}").format(self.server_profile, message or _("reason unknown")))
        else:
            logger.info(_("Disconnected from {}").format(self.server_profile))
        if self.want_to_connect:
            self._reconnect()
        self.set_server_label()

    @ampd.task
    async def _reconnect(self):
        reply = await self.ampd.idle(ampd.CONNECT, timeout=1)
        if reply & ampd.TIMEOUT:
            await self.ampd_client.connect_to_server(self.host, self.port)

    @ampd.task
    async def idle_database(self):
        while True:
            song = await self.ampd.find('file', self.SEPARATOR_FILE)
            if song:
                self.separator_song.update(song[0])
            else:
                GLib.idle_add(self.separator_missing)
            await self.ampd.idle(ampd.DATABASE)
            logger.info(_("Database changed"))

    def separator_missing(self):
        dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.WARNING,
                                   buttons=Gtk.ButtonsType.CLOSE,
                                   text=_("Some features require a file named '{separator}' at the music root directory.  Such a file, consisting of a three second silence, is provided.").format(separator=self.SEPARATOR_FILE))
        dialog.run()
        dialog.destroy()
        return GLib.SOURCE_REMOVE

    def server_error_cb(self, client, error):
        logger.error(_("Server error: {error}").format(error=error))

    def set_server_label(self, *args):
        if not self.want_to_connect:
            self.server_label = _("Not connected")
        elif not self.ampd.get_is_connected():
            self.server_label = _("Connecting to {profile}").format(profile=self.server_profile)
        else:
            self.server_label = self.server_profile
            if self.server_partition and self.server_partition != 'default':
                self.server_label += " {{{}}}".format(self.server_partition)
            if self.ampd_server_properties.updating_db:
                self.server_label += " [{}]".format(_("database update"))

    @staticmethod
    def notify_server_profile_cb(self, param):
        self.set_server_label()

    @staticmethod
    def notify_server_partition_cb(self, param):
        self.set_server_label()

    @staticmethod
    def notify_server_profile_desired_cb(self, param):
        self.config.server.profile_desired = self.server_profile_desired
        self.ampd_connect()
        if self.server_profile_desired != self.server_profile_backup:
            self.config.server_profile_previous = self.server_profile_previous = self.server_profile_backup
            self.server_profile_backup = self.server_profile_desired

    def notify_profiles_cb(self, unit_profiles, param):
        if self.server_profile in self.unit_profiles.profiles and self.want_to_connect and self.host is None:
            GLib.timeout_add(0, self.ampd_connect)
