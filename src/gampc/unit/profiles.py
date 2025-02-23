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
from gi.repository import Gtk

import zeroconf
import zeroconf.asyncio
import re
import asyncio

from ..util import action
from ..util import config
from ..util import misc
from ..util import unit

from ..ui import dialog

from . import mixins


ZEROCONF_MPD_TYPE = '_mpd._tcp.local.'
ZEROCONF_NAME_REGEXP = f'^(?P<name>[^\\[]*)(\\[[0-9]+\\])?\\.{ZEROCONF_MPD_TYPE}$'


class ProfileDialogAsync(dialog.DialogAsync):
    def __init__(self, name, address, used_names, **kwargs):
        super().__init__(**kwargs)

        self.name_entry = Gtk.Entry(text=name)
        self.address_entry = Gtk.Entry(text=address)
        # port_adjustment = Gtk.adjustment(value=port, lower=1024, upper=49150)
        # self.port_spin_button = Gtk.SpingButton(adjustment=port_adjustment)
        box = Gtk.Box()
        box.append(self.name_entry)
        box.append(self.address_entry)
        # box.append(self.port_spin_button)
        self.main_box.prepend(box)
        # self.name_entry.connect('notify::text', self.entry_notify_text_cb)
        # self.address_entry.connect('notify::text', self.entry_notify_text_cb)

    async def run(self):
        result = await super().run()
        # self.name_entry.disconnect_by_func(self.entry_notify_text_cb)
        # self.address_entry.disconnect_by_func(self.entry_notify_text_cb)
        return (self.name_entry.get_text(), self.address_entry.get_text()) if result else (None, None)

    # def entry_notify_text_cb(self, entry, param):
    #     if self.name_entry.get_text() and self.address_entry.get_text():
    #         self.ok_button.set_sensitive(True)
    #     else:
    #         self.ok_button.set_sensitive(False)


class __unit__(mixins.UnitConfigMixin, unit.Unit):
    def __init__(self, manager):
        super().__init__(manager,
                         config.ConfigFixedDict({'profiles': config.ConfigOpenDict(config.ConfigItem(str))}))

        self.menu_zeroconf = Gio.Menu()
        self.menu_localhost = Gio.Menu()
        self.menu_user = Gio.Menu()
        self.menu_user_hosts = Gio.Menu()
        self.menu_user_edit = Gio.Menu()
        self.menu_user_edit_real = Gio.Menu()

        self.zeroconf_profiles_setup()
        self.menu_from_profiles(self.menu_localhost, {_("Local host"): 'localhost:6600'})
        self.user_profiles_setup()

        self.menu = Gio.Menu()
        self.menu.append_section(None, self.menu_zeroconf)
        self.menu.append_section(None, self.menu_localhost)
        self.menu.append_section(None, self.menu_user)
        self.menu_user.append_section(None, self.menu_user_hosts)
        self.menu_user.append_submenu(_("Edit hosts"), self.menu_user_edit)

    def cleanup(self):
        super().cleanup()
        asyncio.get_event_loop().run_until_complete(self.zeroconf_profiles_cleanup())

    def get_edit_action(self):
        return action.ActionInfo('edit-user-profile', self.edit_user_profile_cb, arg_format='(ss)')

    def generate_actions(self):
        yield self.get_edit_action()

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
            self.zc_profiles[short_name] = f'{info.server[:-1]}:{info.port}'
        self.menu_from_profiles(self.menu_zeroconf, self.zc_profiles)

    def user_profiles_setup(self):
        profiles = self.config['profiles']
        self.menu_from_profiles(self.menu_user_hosts, profiles)
        edit_action = self.get_edit_action()
        edit_actions = (edit_action.derive(name, arg=(name, address)) for name, address in profiles.items())
        edit_family = action.ActionInfoFamily(edit_actions, 'app')
        self.menu_user_edit.remove_all()
        self.menu_user_edit.append_section(None, edit_family.get_menu())
        self.menu_user_edit.append_item(edit_action.derive(_("Add profile"), arg=('', '<host>:6600')).get_menu_item('app'))

    @staticmethod
    def menu_from_profiles(menu, profiles):
        base_action = action.ActionInfo('server-profile', None, arg_format='s')
        actions = (base_action.derive(name, arg=f'{address}={name}') for name, address in profiles.items())
        family = action.ActionInfoFamily(actions, 'app')
        menu.remove_all()
        menu.append_section(None, family.get_menu())

    @misc.create_task
    async def edit_user_profile_cb(self, action_, arg):
        name, address = arg.unpack()
        profiles = self.config['profiles']
        used_names = list(profiles)
        if name in used_names:
            used_names.remove(name)
        new_name, new_address = await ProfileDialogAsync(name, address, used_names).run()
        if new_name is None:
            return
        if name != '':
            del profiles[name]
        if new_name != '':
            profiles[new_name] = new_address
        self.user_profiles_setup()
