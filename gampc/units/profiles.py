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


from gi.repository import GObject
from gi.repository import Gio

import zeroconf as zeroconf_  # conflict with handler keyword argument

from gampc.util import ssde
from gampc.util import resource
from gampc.util import unit


ZEROCONF_MPD_TYPE = '_mpd._tcp.local.'


class __unit__(unit.UnitWithConfig):
    REQUIRED_UNITS = ['menubar']

    LOCAL_HOST = _("Local host")

    zeroconf_profiles = GObject.Property()
    user_profiles = GObject.Property()
    profiles = GObject.Property()

    def __init__(self, name, manager):
        super().__init__(name, manager)
        self.config.access('profiles',
                           [
                               {
                                   'name': self.LOCAL_HOST,
                                   'host': 'localhost',
                                   'port': 6600,
                               },
                           ])

        self.zeroconf_profiles = self.user_profiles = self.profiles = {}
        self.connect('notify::zeroconf-profiles', self.notify_profiles_cb)
        self.connect('notify::user-profiles', self.notify_profiles_cb)
        self.zeroconf_profile_menu = Gio.Menu()
        self.user_profile_menu = Gio.Menu()
        self.zeroconf_profiles_setup()
        self.user_profiles_setup()

        self.new_resource_provider('app.action').add_resources(
            resource.ActionModel('edit-user-profiles', self.edit_user_profiles_cb),
        )

        self.new_resource_provider('app.menu').add_resources(
            resource.MenuPath('server/profiles/profiles', _("_Profiles"), is_submenu=True),
            resource.MenuPath('server/profiles/profiles/zeroconf', instance=self.zeroconf_profile_menu),
            resource.MenuPath('server/profiles/profiles/user', instance=self.user_profile_menu),
            resource.MenuAction('server/profiles/profiles/app.edit-user-profiles', _("Edit profiles")),
        )

        self.user_profiles_struct = ssde.List(
            label=_("Profiles"),
            substruct=ssde.Dict(
                label=_("Profile"),
                substructs=[
                    ssde.Text(name='name', label=_("Name")),
                    ssde.Text(name='host', label=_("Host")),
                    ssde.Integer(name='port', label=_("Port"), default=6600, min_value=0),
                ]))

    def shutdown(self):
        super().shutdown()
        self.zeroconf_profiles_cleanup()
        self.disconnect_by_func(self.notify_profiles_cb)
        self.disconnect_by_func(self.notify_profiles_cb)

    def zeroconf_profiles_setup(self):
        self.zeroconf_profile_browser = zeroconf_.ServiceBrowser(zeroconf_.Zeroconf(), ZEROCONF_MPD_TYPE, handlers=[self.zeroconf_profiles_handler])

    def zeroconf_profiles_cleanup(self):
        self.zeroconf_profile_browser.cancel()
        del self.zeroconf_profile_browser

    def zeroconf_profiles_handler(self, zeroconf, service_type, name, state_change):
        info = zeroconf.get_service_info(service_type, name)
        if name.endswith(ZEROCONF_MPD_TYPE):
            name = name[:-len(ZEROCONF_MPD_TYPE) - 1]
        if ' @ ' in name:
            name = name.split(' @ ', 1)[1]
        if state_change == zeroconf_.ServiceStateChange.Added:
            self.zeroconf_profiles[name] = dict(host=info.server, port=info.port)
            self.zeroconf_profiles = self.zeroconf_profiles  # emit notify signal
            resource.MenuAction('app.server-profile-desired("{name}")'.format(name=name), name).insert_into(self.zeroconf_profile_menu)
        elif state_change == zeroconf_.ServiceStateChange.Removed:
            resource.MenuAction('app.server-profile-desired("{name}")'.format(name=name), name).remove_from(self.zeroconf_profile_menu)
            del self.zeroconf_profiles[name]
            self.zeroconf_profiles = self.zeroconf_profiles  # emit notify signal

    def user_profiles_setup(self):
        self.user_profile_menu.remove_all()
        new_user_profiles = {}
        for profile in self.config.profiles:
            resource.MenuAction('app.server-profile-desired("{name}")'.format_map(profile), profile['name']).insert_into(self.user_profile_menu)
            profile = dict(profile)
            name = profile.pop('name')
            new_user_profiles[name] = profile
        self.user_profiles = new_user_profiles

    def edit_user_profiles_cb(self, *args):
        value = self.user_profiles_struct.edit(None, self.config.profiles,
                                               self.config.access(self.unit_config.CONFIG_EDIT_DIALOG_SIZE, [500, 500]))
        if value:
            self.config.profiles = value
            self.user_profiles_setup()

    @staticmethod
    def notify_profiles_cb(self, param):
        new_profiles = {}
        new_profiles.update(self.zeroconf_profiles)
        new_profiles.update(self.user_profiles)
        self.profiles = new_profiles
