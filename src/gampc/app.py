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


from gi.repository import GLib
from gi.repository import Gio
from gi.repository import Gtk

import sys
import logging
import dbus
import signal
import asyncio
import gasyncio
import ampd

from .util import misc
from .util import unit
from .util.logger import logger

from . import __application__, __program_name__, __version__, __copyright__, __license_type__


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=f'begnac.{__application__}', flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE | Gio.ApplicationFlags.ALLOW_REPLACEMENT)

        self.add_main_option('component', ord('c'), GLib.OptionFlags.NONE, GLib.OptionArg.STRING, _("List application actions"), None)
        self.add_main_option('list-actions', 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE, _("List application actions"), None)
        self.add_main_option('version', ord('V'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, _("Display version"), None)
        self.add_main_option('non-unique', ord('u'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, _("Do not start a unique instance"), None)
        self.add_main_option('debug', ord('d'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, _("Debug messages"), None)
        self.add_main_option(GLib.OPTION_REMAINING, 0, GLib.OptionFlags.NONE, GLib.OptionArg.STRING_ARRAY, '', _("[ACTION...]"))

        self.connect('startup', self.startup_cb)
        self.connect('shutdown', self.shutdown_cb)
        self.connect('handle-local-options', self.handle_local_options_cb)
        self.connect('command-line', self.command_line_cb)
        self.connect('activate', self.activate_cb)

    def __del__(self):
        logger.debug(f'Deleting {self}')

    @staticmethod
    def startup_cb(self):
        logger.debug("Starting")

        gasyncio.start_slave_loop()

        self.sigint_source = GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, lambda: self.quit() or True)
        self.excepthook_orig, sys.excepthook = sys.excepthook, self.excepthook

        self.unit_manager = unit.UnitManager()
        # self.unit_manager.set_target('config')
        # self.unit_config = self.unit_manager.get_unit('config')

        default_units = [
            'menubar', 'help', 'profiles', 'server',
            'output', 'persistent',
            'css',
            'playback', 'window',
            'current', 'queue', 'browser', 'search', 'stream', 'playlist', 'tanda',
            'command', 'log'
        ]

        # units = self.unit_manager.get_unit('config').config.access('units', default_units)
        # self.unit_config.config.units =
        self.unit_manager.set_target(*default_units)

        self.unit_server = self.unit_manager.get_unit('server')
        self.unit_persistent = self.unit_manager.get_unit('persistent')
        self.unit_component = self.unit_manager.get_unit('component')
        self.unit_window = self.unit_manager.get_unit('window')

        self.unit_window.app = self

        self.ampd = self.unit_server.ampd.sub_executor()

        self.notification = Gio.Notification.new(_("MPD status"))
        self.notification_task = None

        self.session_inhibit_cookie = None
        self.systemd_inhibit_fd = None
        self.unit_server.ampd_server_properties.connect('notify::state', self.set_inhibit)

        self.unit_server.ampd_connect()

        self.connect('window-removed', lambda self, window: window.cleanup())

    @staticmethod
    def shutdown_cb(self):
        logger.debug("Shutting down")

        for window in self.get_windows():
            window.destroy()

        misc.get_clipboard().set_content(None)

        self.unit_server.ampd_server_properties.disconnect_by_func(self.set_inhibit)
        self.unit_manager.set_target()
        del self.unit_manager

        del self.unit_window.app

        # for name in self.list_actions():
        #     self.remove_action(name)

        for name in self.list_actions():
            self.remove_action(name)
        sys.excepthook = self.excepthook_orig
        del self.excepthook_orig

        gasyncio.stop_slave_loop()

        GLib.source_remove(self.sigint_source)

    @staticmethod
    def handle_local_options_cb(self, options):
        if options.contains('version'):
            print(_("{program} version {version}").format(program=__program_name__, version=__version__))
            print(__copyright__)
            print(__license_type__)
            return 0

        if options.contains('list-actions'):
            self.register()
            for name in sorted(self.list_actions()):
                print(name)
            return 0

        if options.contains('non-unique'):
            self.set_flags(self.get_flags() | Gio.ApplicationFlags.NON_UNIQUE)

        if options.contains('debug'):
            logging.getLogger().setLevel(logging.DEBUG)

        return -1

    @staticmethod
    def command_line_cb(self, command_line):
        options = command_line.get_options_dict().end().unpack()
        if 'component' in options:
            self.unit_window.new_window(options['component'])
        elif GLib.OPTION_REMAINING in options:
            for option in options[GLib.OPTION_REMAINING]:
                try:
                    success, name, target = Gio.Action.parse_detailed_name(option)
                except Exception as e:
                    logger.error(e)
                    continue
                if not self.has_action(name):
                    logger.error(_("Action '{name}' does not exist").format(name=name))
                else:
                    self.activate_action(name, target)
        else:
            self.activate()
        return 0

    @staticmethod
    def activate_cb(self):
        win = self.get_active_window()
        if win:
            win.present()
        else:
            self.activate_action('new-window')

    @staticmethod
    def excepthook(*args):
        if args[0] == ampd.errors.ReplyError:
            logger.error(args[1])
        else:
            logger.error(args[1], exc_info=args)
        try:
            del sys.last_type, sys.last_value, sys.last_traceback
        except AttributeError:
            pass

    @ampd.task
    async def action_notify_cb(self, *args):
        if self.notification_task:
            self.notification_task._close()
            self.withdraw_notification('status')
        self.notification_task = asyncio.current_task()
        await self.ampd.idle(ampd.IDLE)
        if self.unit_server.ampd_server_properties.state == 'stop':
            icon_name = 'media-playback-stop-symbolic'
            body = 'Stopped'
        else:
            if self.unit_server.ampd_server_properties.state == 'play':
                icon_name = 'media-playback-start-symbolic'
            else:
                icon_name = 'media-playback-pause-symbolic'
            body = '{0} / {1}'.format(self.unit_server.ampd_server_properties.current_song.get('Artist', '???'), self.unit_server.ampd_server_properties.current_song.get('Title', '???'))
            if 'performer' in self.unit_server.ampd_server_properties.current_song:
                body += ' / ' + self.unit_server.ampd_server_properties.current_song['Performer']
        self.notification.set_body(body)
        self.notification.set_icon(Gio.Icon.new_for_string(icon_name))
        self.send_notification('status', self.notification)
        await asyncio.sleep(5)
        self.withdraw_notification('status')
        self.notification_task = None

    def set_inhibit(self, *args):
        if self.unit_server.ampd_server_properties.state == 'play':
            self.session_inhibit_cookie = self.session_inhibit_cookie or self.inhibit(None, Gtk.ApplicationInhibitFlags.SUSPEND | Gtk.ApplicationInhibitFlags.IDLE, __program_name__)
            bus = dbus.SystemBus()
            obj = bus.get_object('org.freedesktop.login1', '/org/freedesktop/login1')
            self.systemd_inhibit_fd = self.systemd_inhibit_fd or obj.Inhibit('handle-lid-switch', __program_name__, _("Playing"), 'block', dbus_interface='org.freedesktop.login1.Manager')
        else:
            self.session_inhibit_cookie = self.session_inhibit_cookie and self.uninhibit(self.session_inhibit_cookie)
            self.systemd_inhibit_fd = None

    def follow_action_group(self, action_group):
        for name in action_group.list_actions():
            self.add_action(action_group.lookup_action(name))
        action_group.connect('action-added', self.follow_action_added_cb)
        action_group.connect('action-removed', self.follow_action_removed_cb)

    def follow_action_added_cb(self, action_group, name):
        self.add_action(action_group.lookup_action(name))

    def follow_action_removed_cb(self, action_group, name):
        self.remove_action(name)
