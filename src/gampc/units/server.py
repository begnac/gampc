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


from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

import asyncio
import ampd

from ..util import resource
from ..util import unit
from ..util.logger import logger


class ServerOption(GObject.Object):
    value = GObject.Property(type=bool, default=False)


class __unit__(unit.UnitMixinConfig, unit.Unit):
    REQUIRED_UNITS = ['menubar', 'profiles']

    SEPARATOR_FILE = 'separator.mp3'

    server_label = GObject.Property(type=str, default='')
    server_profile = GObject.Property(type=str)

    current_song = GObject.Property()

    def __init__(self, name, manager):
        super().__init__(name, manager)
        self.current_song_hooks = []
        self.ampd_client = ampd.ClientGLib()
        self.ampd_client.connect('client-connected', self.client_connected_cb)
        self.ampd_client.connect('client-disconnected', self.client_disconnected_cb)

        self.ampd = self.ampd_client.executor.sub_executor()

        self.ampd_server_properties = ampd.ServerPropertiesGLib(self.ampd_client.executor)
        self.ampd_server_properties.bind_property('current-song', self, 'current-song', GObject.BindingFlags.SYNC_CREATE, self.current_song_transform)
        self.ampd_server_properties.connect('server-error', self.server_error_cb)
        self.ampd_server_properties.connect('notify::updating-db', self.set_server_label)
        self.server_options = {name: ServerOption() for name in ampd.OPTION_NAMES}
        for name in ampd.OPTION_NAMES:
            self.ampd_server_properties.bind_property(name, self.server_options[name], 'value', GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)

        self.want_to_connect = False

        self.server_profile = self.config.server_profile._get(default=self.unit_profiles.LOCAL_HOST_NAME)
        self.server_profile_previous = self.config.server_profile_previous._get(default=self.server_profile)
        self.server_profile_backup = self.server_profile

        self.profile = self.unit_profiles.profile_from_repr(self.server_profile)
        self.set_server_label()

        self.connect('notify::server-profile', self.notify_server_profile_cb)

        self.separator_song = {'file': self.SEPARATOR_FILE}

        self.add_resources(
            'app.action',
            resource.PropertyActionModel('server-profile', self),
            resource.ActionModel('connect', self.ampd_connect),
            resource.ActionModel('disconnect', self.ampd_disconnect),
            resource.ActionModel('connect-to-previous', self.ampd_connect_to_previous),
            resource.ActionModel('update', self.update_cb),
            *(resource.PropertyActionModel(name, self.server_options[name], property_name='value') for name in ampd.OPTION_NAMES)
        )

        self.add_resources(
            'app.menu',
            resource.MenuPath('server/server/actions'),
            resource.MenuPath('server/server/output'),
            resource.MenuPath('server/server/connection'),
            resource.MenuAction('server/server/actions', 'app.update', _("Update database")),
            resource.MenuAction('server/server/connection', 'app.connect', _("Connect"), ['<Alt><Shift>c']),
            resource.MenuAction('server/server/connection', 'app.disconnect', _("Disconnect"), ['<Alt><Shift>d']),
            resource.MenuAction('server/server/connection', 'app.connect-to-previous', _("Connect to previous"), ['<Control><Alt>p']),
        )

    def shutdown(self):
        if self.current_song_hooks:
            raise RuntimeError
        self.want_to_connect = False
        asyncio.get_event_loop().run_without_glib_until_complete(self.ampd_client.close())
        self.disconnect_by_func(self.notify_server_profile_cb)
        self.ampd_client.disconnect_by_func(self.client_disconnected_cb)
        self.ampd_client.disconnect_by_func(self.client_connected_cb)
        self.ampd_server_properties.disconnect_by_func(self.set_server_label)
        self.ampd_server_properties.disconnect_by_func(self.server_error_cb)
        del self.ampd_client
        del self.ampd_server_properties
        super().shutdown()

    def ampd_connect(self, *args):
        self.want_to_connect = True
        asyncio.ensure_future(self.ampd_client.connect_to_server(self.profile.address))
        self.set_server_label()

    def ampd_disconnect(self, *args):
        self.want_to_connect = False
        asyncio.ensure_future(self.ampd_client.disconnect_from_server())
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
        self.idle_database()

    def client_disconnected_cb(self, client, reason, message):
        self.separator_song.clear()
        self.separator_song['file'] = self.SEPARATOR_FILE
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
        reply = await self.ampd.idle(ampd.CONNECT, timeout=1)
        if reply & ampd.TIMEOUT:
            await self.ampd_client.connect_to_server(self.profile.address)

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

    def add_current_song_hook(self, hook, priority=None):
        self.current_song_hooks.append(hook)
        self.current_song = self.current_song_transform(None, self.ampd_server_properties.current_song)

    def remove_current_song_hook(self, hook):
        self.current_song_hooks.remove(hook)
        self.current_song = self.current_song_transform(None, self.ampd_server_properties.current_song)

    def current_song_transform(self, binding, song):
        song = song.copy()
        for hook in self.current_song_hooks:
            hook(song)
        return song
