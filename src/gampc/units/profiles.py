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


from gi.repository import Gio

import zeroconf
import zeroconf.asyncio
import re
import asyncio

from ..util import ssde
from ..util import resource
from ..util import unit


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
        return resource.MenuActionMinimal(f'app.server-profile("{self}")', self.name)

    def __repr__(self):
        return f'{self.address}={self.name}'


class __unit__(unit.UnitMixinConfig, unit.Unit):
    REQUIRED_UNITS = ['menubar']

    LOCAL_HOST_NAME = _("Local host")
    LOCAL_HOST_ADDRESS = 'localhost:6600'

    def __init__(self, name, manager):
        super().__init__(name, manager)
        default_profiles = [
            {
                'name': self.LOCAL_HOST_NAME,
                'address': self.LOCAL_HOST_ADDRESS,
            },
        ]

        self.zeroconf_profile_menu = Gio.Menu()
        self.user_profile_menu = Gio.Menu()
        self.zeroconf_profiles_setup()

        self.config.profiles._get(default=default_profiles)
        self.user_profiles_setup()

        self.add_resources(
            'app.action',
            resource.ActionModel('edit-user-profiles', self.edit_user_profiles_cb),
        )

        self.add_resources(
            'app.menu',
            resource.MenuPath('server/profiles/profiles_menu', _("_Profiles"), is_submenu=True),
            resource.MenuPath('server/profiles/profiles_menu/zeroconf', instance=self.zeroconf_profile_menu),
            resource.MenuPath('server/profiles/profiles_menu/user', instance=self.user_profile_menu),
            resource.MenuAction('server/profiles/profiles_menu', 'app.edit-user-profiles', _("Edit profiles")),
        )

        self.user_profiles_struct = ssde.List(
            label=_("Profiles"),
            substruct=ssde.Dict(
                label=_("Profile"),
                substructs=[
                    ssde.Text(name='name', label=_("Name"), default=_("<Name>")),
                    ssde.Text(name='address', label=_("[password@]host:port"), default=_("<Host>") + ':6600'),
                ]))

    def shutdown(self):
        super().shutdown()
        asyncio.get_event_loop().run_until_complete(self.zeroconf_profiles_cleanup())

    def zeroconf_profiles_setup(self):
        self.zc_menu_actions = {}
        self.azc = zeroconf.asyncio.AsyncZeroconf()
        self.asb = zeroconf.asyncio.AsyncServiceBrowser(self.azc.zeroconf, ZEROCONF_MPD_TYPE, handlers=[lambda **kwargs: asyncio.ensure_future(self.zeroconf_profiles_handler(**kwargs))])

    async def zeroconf_profiles_cleanup(self):
        await self.asb.async_cancel()
        await self.azc.async_close()

        del self.azc.zeroconf.engine
        del self.azc.zeroconf.record_manager
        del self.azc.zeroconf._out_queue
        del self.azc.zeroconf._out_delay_queue
        del self.asb

    async def zeroconf_profiles_handler(self, service_type, name, state_change, **kwargs):
        match = re.fullmatch(ZEROCONF_NAME_REGEXP, name)
        short_name = match.group('name')
        if state_change in (zeroconf.ServiceStateChange.Removed, zeroconf.ServiceStateChange.Updated) and short_name in self.zc_menu_actions:
            menu_action = self.zc_menu_actions.pop(short_name)
            menu_action.remove_from(self.zeroconf_profile_menu)
        if state_change in (zeroconf.ServiceStateChange.Added, zeroconf.ServiceStateChange.Updated) and short_name not in self.zc_menu_actions:
            info = await self.azc.async_get_service_info(service_type, name)
            profile = Profile(short_name, f'{info.server[:-1]}:{info.port}')
            menu_action = profile.get_action()
            menu_action.insert_into(self.zeroconf_profile_menu)
            self.zc_menu_actions[short_name] = menu_action

    def user_profiles_setup(self):
        self.user_profile_menu.remove_all()
        for profile in self.config.profiles._get():
            Profile(**profile).get_action().insert_into(self.user_profile_menu)

    def edit_user_profiles_cb(self, *args):
        value = self.user_profiles_struct.edit(None, self.config.profiles._get(), self.config.edit_dialog_size._get(default=[500, 500]))
        if value:
            self.config.profiles._set(value)
            self.user_profiles_setup()

    profile_from_repr = staticmethod(Profile.from_repr)
