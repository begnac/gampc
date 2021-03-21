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
from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import Gtk

import sys
import logging
import dbus
import signal
import asyncio
import gasyncio
import ampd

from . import __program_name__, __version__, __program_description__, __copyright__, __license__
from .util import unit
from .util import resource
from .util.logger import logger


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='begnac.gampc', flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)

        self.add_main_option('list-actions', 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE, _("List application actions"), None)
        self.add_main_option('version', 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE, _("Display version"), None)
        self.add_main_option('copyright', 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE, _("Display copyright"), None)
        self.add_main_option('non-unique', ord('u'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, _("Do not start a unique instance"), None)
        self.add_main_option('debug', ord('d'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, _("Debug messages"), None)
        self.add_main_option(GLib.OPTION_REMAINING, 0, GLib.OptionFlags.NONE, GLib.OptionArg.STRING_ARRAY, '', _("[ACTION...]"))

    def __del__(self):
        logger.debug('Deleting {}'.format(self))

    def run(self, argv):
        self.connect('startup', self.startup_cb),
        self.connect('shutdown', self.shutdown_cb),
        self.connect('handle-local-options', self.handle_local_options_cb),
        self.connect('command-line', self.command_line_cb),
        self.connect('activate', self.activate_cb),
        super().run(argv)

    @staticmethod
    def startup_cb(self):
        logger.debug("Starting")

        self.event_loop = gasyncio.GAsyncIOEventLoop()
        self.event_loop.start_slave_loop()

        self.sigint_source = GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, lambda: self.quit() or True)
        self.excepthook_orig, sys.excepthook = sys.excepthook, self.excepthook

        self.menubar = Gio.Menu()
        self.set_menubar(self.menubar)

        self.unit_manager = unit.UnitManager()
        self.unit_manager.set_target('config')
        default_units = ['config', 'menubar', 'misc', 'profiles', 'server', 'partition', 'persistent', 'playback',
                         'module', 'window',
                         'modules.current', 'modules.playqueue', 'modules.browser', 'modules.search', 'modules.stream', 'modules.playlist', 'modules.command', 'modules.log', 'modules.savedsearch']
        units = self.unit_manager.get_unit('config').config.access('units', default_units)
        self.unit_manager.set_target(*units)

        self.unit_misc = self.unit_manager.get_unit('misc')
        self.unit_server = self.unit_manager.get_unit('server')
        self.unit_persistent = self.unit_manager.get_unit('persistent')
        self.unit_module = self.unit_manager.get_unit('module')
        self.unit_window = self.unit_manager.get_unit('window')

        self.action_aggregator = self.unit_manager.create_aggregator('app.action', self.action_added_cb, self.action_removed_cb),
        self.menu_aggregator = self.unit_manager.create_aggregator('app.menu', self.menu_added_cb, self.menu_removed_cb),
        self.user_action_aggregator = self.unit_manager.create_aggregator('app.user-action', self.user_action_added_cb, self.user_action_removed_cb)

        self.unit_misc.connect('notify::block-fragile-accels', self.notify_block_fragile_accels_cb)

        self.ampd = self.unit_server.ampd.sub_executor()

        self.notification = Gio.Notification.new(_("MPD status"))
        self.notification_task = None

        self.session_inhibit_cookie = None
        self.systemd_inhibit_fd = None
        self.unit_server.ampd_server_properties.connect('notify::state', self.set_inhibit)
        self.unit_persistent.connect('notify::protected', self.set_inhibit)

        self.add_action(resource.Action('new-window', self.new_window_cb))
        self.add_action(resource.Action('close-window', self.close_window_cb))
        self.add_action(resource.Action('help', self.help_cb))
        self.add_action(resource.Action('about', self.about_cb))
        self.add_action(resource.Action('notify', self.task_hold_app(self.action_notify_cb)))
        self.add_action(resource.Action('quit', self.quit))
        self.add_action(resource.Action('module-start', self.module_start_cb, parameter_type=GLib.VariantType.new('s')))
        self.add_action(resource.Action('module-start-new-window', self.module_start_cb, parameter_type=GLib.VariantType.new('s')))
        self.add_action(resource.Action('module-stop', self.module_stop_cb))

        # self.add_action(resource.Action('BAD', self.THIS_IS_BAD_cb))

        self.unit_server.ampd_connect()

    @staticmethod
    def shutdown_cb(self):
        logger.debug("Shutting down")
        self.unit_server.ampd_server_properties.disconnect_by_func(self.set_inhibit)
        self.unit_persistent.disconnect_by_func(self.set_inhibit)
        self.unit_misc.disconnect_by_func(self.notify_block_fragile_accels_cb)
        self.unit_manager.set_target()
        del self.unit_manager
        del self.user_action_aggregator
        del self.menu_aggregator
        del self.action_aggregator

        del self.unit_window
        del self.unit_module
        del self.unit_persistent
        del self.unit_server
        del self.unit_misc

        for name in self.list_actions():
            self.remove_action(name)
        self.set_menubar()
        del self.menubar
        sys.excepthook = self.excepthook_orig
        del self.excepthook_orig

        self.event_loop.stop_slave_loop()
        self.event_loop.stop()
        self.event_loop.close()

        GLib.source_remove(self.sigint_source)

    @staticmethod
    def handle_local_options_cb(self, options):
        if options.contains('non-unique'):
            self.set_flags(self.get_flags() | Gio.ApplicationFlags.NON_UNIQUE)
        if options.contains('debug'):
            logging.getLogger().setLevel(logging.DEBUG)
        if options.contains('version'):
            print(_("{program} version {version}").format(program=__program_name__, version=__version__))
        elif options.contains('copyright'):
            print(__copyright__)
            print(__license__)
        elif options.contains('list-actions'):
            self.register()
            for name in sorted(self.list_actions()):
                print(name)
        else:
            return -1
        return 0

    @staticmethod
    def command_line_cb(self, command_line):
        options = command_line.get_options_dict().end().unpack()
        if GLib.OPTION_REMAINING in options:
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
    def activate_cb(self, *args):
        win = self.get_active_window()
        if win:
            win.present()
        else:
            self.new_window_cb(None, None)

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

    def task_hold_app(self, f):
        def g(*args, **kwargs):
            retval = f(*args, **kwargs)
            if isinstance(retval, asyncio.Future):
                self.hold()
                retval.add_done_callback(lambda future: self.release())
            return retval
        return g

    def notify_block_fragile_accels_cb(self, unit_misc, param):
        for user_action in self.user_action_aggregator.get_resources():
            self.set_accels_for_action(user_action.action, [] if self.unit_misc.block_fragile_accels and user_action.accels_fragile else user_action.accels)

    def action_added_cb(self, aggregator, action):
        self.add_action(action.generate(self.task_hold_app, self.unit_persistent))

    def action_removed_cb(self, aggregator, action):
        self.remove_action(action.get_name())

    def menu_added_cb(self, aggregator, menu):
        menu.insert_into(self.menubar)

    def menu_removed_cb(self, aggregator, menu):
        menu.remove_from(self.menubar)

    def user_action_added_cb(self, aggregator, user_action):
        user_action.get_menu_action().insert_into(self.menubar)
        if not self.unit_misc.block_fragile_accels or not user_action.accels_fragile:
            self.set_accels_for_action(user_action.action, user_action.accels)

    def user_action_removed_cb(self, aggregator, user_action):
        user_action.get_menu_action().remove_from(self.menubar)
        self.set_accels_for_action(user_action.action, [])

    def new_window_cb(self, action, parameter):
        module = self.unit_module.get_module('current', False)
        self.display_module(module, True)

    def close_window_cb(self, action, parameter):
        self.get_active_window().destroy()

    def module_start_cb(self, action, parameter):
        module = self.unit_module.get_module(parameter.unpack(), Gdk.Keymap.get_default().get_modifier_state() & Gdk.ModifierType.CONTROL_MASK)
        self.display_module(module, action.get_name().endswith('new-window'))

    def display_module(self, module, new_window):
        win = None if new_window else module.win or self.get_active_window()
        if win is None:
            win = self.unit_window.new_window(self)
        if module.win is None:
            win.change_module(module)
        win.present()

    def module_stop_cb(self, action, parameter):
        win = self.get_active_window()
        module = win.module
        if module:
            win.change_module(self.unit_module.get_free_module())
            self.unit_module.remove_module(module)

    def quit(self, *args):
        logger.debug("Quit")
        for win in self.get_windows():
            win.destroy()
        return True

    def about_cb(self, *args):
        dialog = Gtk.AboutDialog(parent=self.get_active_window(), program_name=__program_name__, version=__version__, comments=__program_description__, copyright=__copyright__, license_type=Gtk.License.GPL_3_0, logo_icon_name='face-cool', website='http://math.univ-lyon1.fr/~begnac', website_label=_("Author's website"))
        dialog.run()
        dialog.destroy()

    def help_cb(self, *args):
        window = Gtk.ShortcutsWindow(title="Window", transient_for=self.get_active_window(), modal=True)
        # window.set_application(self)

        section = Gtk.ShortcutsSection(title="Section", section_name="CC")
        section.show()
        window.add(section)

        group = Gtk.ShortcutsGroup(title="Group")
        section.add(group)

        for user_action in self.user_action_aggregator.get_resources():
            if not user_action.accels:
                continue
            shortcut = Gtk.ShortcutsShortcut(accelerator=' '.join(user_action.accels),
                                             title=user_action.label)
            group.add(shortcut)

        window.show_all()

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

    def THIS_IS_BAD_cb(self, action, param):
        pass
        # window = Gtk.ShortcutsWindow(title="Window", transient_for=self.get_active_window(), modal=True)
        # # window.set_application(self)

        # section = Gtk.ShortcutsSection(title="Section", section_name="CC")
        # section.show()
        # window.add(section)

        # group = Gtk.ShortcutsGroup(title="Group")
        # section.add(group)

        # for user_action in self.user_action_aggregator.get_resources():
        #     if not user_action.accels:
        #         continue
        #     shortcut = Gtk.ShortcutsShortcut(accelerator=' '.join(user_action.accels),
        #                                      title=user_action.label)
        #     group.add(shortcut)

        # window.show_all()
