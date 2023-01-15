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

    def do_startup(self):
        Gtk.Application.do_startup(self)

        logger.debug("Starting")

        self.event_loop = gasyncio.GAsyncIOEventLoop()
        self.event_loop.start_slave_loop()

        self.sigint_source = GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, lambda: self.quit() or True)
        self.excepthook_orig, sys.excepthook = sys.excepthook, self.excepthook

        self.menubar = Gio.Menu()
        self.set_menubar(self.menubar)

        self.unit_manager = unit.UnitManager()
        # self.unit_manager.set_target('config')
        # self.unit_config = self.unit_manager.get_unit('config')

        default_units = [
            'menubar', 'misc', 'profiles', 'server',
            'output', 'persistent',
            'playback', 'window',
            'current', 'playqueue', 'browser', 'search', 'stream', 'playlist', 'tanda', 'command', 'log'
        ]

        # units = self.unit_manager.get_unit('config').config.access('units', default_units)
        # self.unit_config.config.units =
        self.unit_manager.set_target(*default_units)

        self.unit_misc = self.unit_manager.get_unit('misc')
        self.unit_server = self.unit_manager.get_unit('server')
        self.unit_persistent = self.unit_manager.get_unit('persistent')
        self.unit_component = self.unit_manager.get_unit('component')
        self.unit_window = self.unit_manager.get_unit('window')

        self.action_aggregator = self.unit_manager.create_aggregator('app.action', self.action_added_cb, self.action_removed_cb)
        self.menu_aggregator = self.unit_manager.create_aggregator('app.menu', self.menu_item_added_cb, self.menu_item_removed_cb)

        self.unit_misc.connect('notify::block-fragile-accels', self.notify_block_fragile_accels_cb)

        self.ampd = self.unit_server.ampd.sub_executor()

        self.notification = Gio.Notification.new(_("MPD status"))
        self.notification_task = None

        self.session_inhibit_cookie = None
        self.systemd_inhibit_fd = None
        self.unit_server.ampd_server_properties.connect('notify::state', self.set_inhibit)

        self.add_action(resource.Action('new-window', self.new_window_cb))
        self.add_action(resource.Action('close-window', self.close_window_cb))
        self.add_action(resource.Action('help', self.help_cb))
        self.add_action(resource.Action('about', self.about_cb))
        self.add_action(resource.Action('notify', self.task_hold_app(self.action_notify_cb)))
        self.add_action(resource.Action('quit', self.quit))
        self.add_action(resource.Action('component-start', self.component_start_cb, parameter_type=GLib.VariantType.new('s')))
        self.add_action(resource.Action('component-start-new-window', self.component_start_cb, parameter_type=GLib.VariantType.new('s')))
        self.add_action(resource.Action('component-stop', self.component_stop_cb))

        self.unit_server.ampd_connect()

    def do_shutdown(self):
        logger.debug("Shutting down")

        self.unit_server.ampd_server_properties.disconnect_by_func(self.set_inhibit)
        self.unit_misc.disconnect_by_func(self.notify_block_fragile_accels_cb)
        self.unit_manager.set_target()
        del self.unit_manager
        del self.menu_aggregator
        del self.action_aggregator

        del self.unit_window
        del self.unit_component
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
        self.event_loop.close()

        GLib.source_remove(self.sigint_source)

        Gtk.Application.do_shutdown(self)

    def do_handle_local_options(self, options):
        if options.contains('version'):
            print(_("{program} version {version}").format(program=__program_name__, version=__version__))
            return 0

        if options.contains('copyright'):
            print(__copyright__)
            print(__license__)
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

        return Gtk.Application.do_handle_local_options(self, options)

    def do_command_line(self, command_line):
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

    def do_activate(self):
        Gtk.Application.do_activate(self)
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
        for menu_item in self.menu_aggregator.get_resources():
            if isinstance(menu_item, resource.UserAction):
                self.set_accels_for_action(menu_item.action, [] if self.unit_misc.block_fragile_accels and menu_item.accels_fragile else menu_item.accels)

    def action_added_cb(self, aggregator, action):
        self.add_action(action.generate(self.task_hold_app, self.unit_persistent))

    def action_removed_cb(self, aggregator, action):
        self.remove_action(action.get_name())

    def menu_item_added_cb(self, aggregator, menu_item):
        menu_item.insert_into(self.menubar)
        if isinstance(menu_item, resource.UserAction) and not (self.unit_misc.block_fragile_accels and menu_item.accels_fragile):
            self.set_accels_for_action(menu_item.action, menu_item.accels)

    def menu_item_removed_cb(self, aggregator, menu_item):
        menu_item.remove_from(self.menubar)
        if isinstance(menu_item, resource.UserAction):
            self.set_accels_for_action(menu_item.action, [])

    def new_window_cb(self, action, parameter):
        component = self.unit_component.get_component('current', False)
        self.display_component(component, True)

    def close_window_cb(self, action, parameter):
        self.get_active_window().destroy()

    def component_start_cb(self, action, parameter):
        component = self.unit_component.get_component(parameter.unpack(), Gdk.Keymap.get_default().get_modifier_state() & Gdk.ModifierType.CONTROL_MASK)
        self.display_component(component, action.get_name().endswith('new-window'))

    def display_component(self, component, new_window):
        win = None if new_window else component.win or self.get_active_window()
        if win is None:
            win = self.unit_window.new_window(self)
        if component.win is None:
            win.change_component(component)
        win.present()

    def component_stop_cb(self, action, parameter):
        win = self.get_active_window()
        component = win.component
        if component:
            win.change_component(self.unit_component.get_free_component())
            self.unit_component.remove_component(component)

    def quit(self, *args):
        logger.debug("Quit")
        for win in self.get_windows():
            win.destroy()
        super().quit()
        return True

    def about_cb(self, *args):
        dialog = Gtk.AboutDialog(parent=self.get_active_window(), program_name=__program_name__, version=__version__, comments=__program_description__, copyright=__copyright__, license_type=Gtk.License.GPL_3_0, logo_icon_name='face-cool-gampc', website='http://math.univ-lyon1.fr/~begnac', website_label=_("Author's website"))
        dialog.run()
        dialog.destroy()

    def help_cb(self, *args):
        window = Gtk.ShortcutsWindow(title="Window", transient_for=self.get_active_window(), modal=True)
        # window.set_application(self)

        section_labels = {}
        section_order = []
        items_by_section = {}
        for menu_item in self.menu_aggregator.get_resources():
            if '/' not in menu_item.path:
                section_labels[menu_item.path] = menu_item.label.replace('_', '')
                section_order.append(menu_item.path)
            elif isinstance(menu_item, resource.UserAction) and menu_item.accels:
                print(menu_item.name, self.lookup_action(menu_item.name.split('.')[1]))
                name = menu_item.path[:menu_item.path.find('/')]
                if name not in items_by_section:
                    items_by_section[name] = []
                items_by_section[name].append(menu_item)

        section = Gtk.ShortcutsSection(title=None, section_name='section', visible=True)
        window.add(section)

        for name in section_order:
            if name not in items_by_section:
                continue
            group = Gtk.ShortcutsGroup(title=section_labels[name], name=name, visible=True)
            section.add(group)

            for menu_item in items_by_section[name]:
                shortcut = Gtk.ShortcutsShortcut(accelerator=' '.join(menu_item.accels),
                                                 title=menu_item.label.replace('_', ''), visible=True)
                group.add(shortcut)

        window.show()

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
