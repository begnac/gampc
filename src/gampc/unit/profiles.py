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


from gi.repository import Gio

import zeroconf
import zeroconf.asyncio
import re
import asyncio

from ..util import action
from ..util import unit

from ..ui import ssde

from . import mixins


ZEROCONF_MPD_TYPE = '_mpd._tcp.local.'
ZEROCONF_NAME_REGEXP = f'^(?P<name>[^\\[]*)(\\[[0-9]+\\])?\\.{ZEROCONF_MPD_TYPE}$'


class Profile:
    def __init__(self, name, address=None):
        self.name = name
        self.address = address

    @staticmethod
    def from_repr(profile_repr):
        if '=' in profile_repr:
            address, name = profile_repr.split('=', 1)
        else:
            address = profile_repr
            name = _("Unknown profile")
        return Profile(name, address)

    def get_action(self):
        return action.ActionInfo('server-profile', None, self.name, arg=repr(self), arg_format='s')

    def __repr__(self):
        return f'{self.address}={self.name}'


class __unit__(mixins.UnitConfigMixin, unit.Unit):
    LOCAL_HOST_NAME = _("Local host")
    LOCAL_HOST_ADDRESS = 'localhost:6600'

    def __init__(self, manager):
        super().__init__(manager)

        self.user_profiles_struct = ssde.List(
            label=_("Profiles"),
            substruct=ssde.Dict(
                label=_("Profile"),
                substructs=[
                    ssde.Text(name='name', label=_("Name"), default=_("<Name>")),
                    ssde.Text(name='address', label=_("[password@]host:port"), default=_("<Host>") + ':6600'),
                ]))

        default_profiles = [
            {
                'name': self.LOCAL_HOST_NAME,
                'address': self.LOCAL_HOST_ADDRESS,
            },
        ]

        self.config.profiles._get(default=default_profiles)

        self.zeroconf_menu = Gio.Menu()
        self.zeroconf_profiles_setup()

        self.user_menu = Gio.Menu()
        self.user_profiles_setup()

        self.menu = Gio.Menu()
        self.menu.append_section(None, self.zeroconf_menu)
        self.menu.append_section(None, self.user_menu)

    def cleanup(self):
        super().cleanup()
        asyncio.get_event_loop().run_until_complete(self.zeroconf_profiles_cleanup())

    def generate_actions(self):
        yield action.ActionInfo('edit-user-profiles', self.edit_user_profiles_cb, _("Edit profiles"))

    def zeroconf_profiles_setup(self):
        self.zc_profiles = {}
        self.azc = zeroconf.asyncio.AsyncZeroconf()
        self.asb = zeroconf.asyncio.AsyncServiceBrowser(self.azc.zeroconf, ZEROCONF_MPD_TYPE, handlers=[lambda **kwargs: asyncio.create_task(self.zeroconf_profiles_handler(**kwargs))])

    async def zeroconf_profiles_cleanup(self):
        await self.asb.async_cancel()
        del self.asb
        await self.azc.async_close()
        del self.azc.zeroconf.engine
        del self.azc.zeroconf.out_queue
        del self.azc.zeroconf.out_delay_queue
        del self.azc.zeroconf.query_handler
        del self.azc.zeroconf.record_manager

    async def zeroconf_profiles_handler(self, *, service_type, name, state_change, **kwargs):
        match = re.fullmatch(ZEROCONF_NAME_REGEXP, name)
        short_name = match.group('name')
        if state_change in (zeroconf.ServiceStateChange.Removed, zeroconf.ServiceStateChange.Updated) and short_name in self.zc_profiles:
            self.zc_profiles.pop(short_name)
        if state_change in (zeroconf.ServiceStateChange.Added, zeroconf.ServiceStateChange.Updated) and short_name not in self.zc_profiles:
            info = await self.azc.async_get_service_info(service_type, name)
            self.zc_profiles[short_name] = Profile(short_name, f'{info.server[:-1]}:{info.port}').get_action()
        family = action.ActionInfoFamily(self.zc_profiles.values(), 'app')
        self.zeroconf_menu.remove_all()
        self.zeroconf_menu.append_section(None, family.get_menu())

    def user_profiles_setup(self):
        family = action.ActionInfoFamily((Profile(**profile).get_action() for profile in self.config.profiles._get()), 'app')
        self.user_menu.remove_all()
        self.user_menu.append_section(None, family.get_menu())

    def edit_user_profiles_cb(self, *args):
        value = self.user_profiles_struct.edit(None, self.config.profiles._get(), self.config.edit_dialog_size._get(default=[500, 500]))
        if value:
            self.config.profiles._set(value)
            self.user_profiles_setup()

    profile_from_repr = staticmethod(Profile.from_repr)
