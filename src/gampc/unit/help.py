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


from gi.repository import Gtk

from ..util import action
from ..util import unit

from .. import __program_name__, __version__, __program_description__, __copyright__, __license_type__, __website__


def iterate_children(widget):
    yield widget
    for child in widget:
        yield from iterate_children(child)


def iterate_help_controllers(widget):
    for child in iterate_children(widget):
        for controller in child.observe_controllers():
            if isinstance(controller, action.ShortcutControllerWithHelp):
                yield controller


class ShortcutsWindow(Gtk.ShortcutsWindow):
    def __init__(self, window):
        super().__init__(modal=True, destroy_with_parent=True, transient_for=window)

        groups_app = {}
        groups_other = {}

        section_app = Gtk.ShortcutsSection(title=_("Application shortcuts"), section_name='app')
        section_other = Gtk.ShortcutsSection(title=_("Window shortcuts"), section_name='win')

        for controller in iterate_help_controllers(window):
            if controller.prefix == 'app':
                groups, section = groups_app, section_app
            else:
                groups, section = groups_other, section_other
            for shortcut in controller:
                if isinstance(shortcut, action.ShortcutWithHelp) and shortcut.accels is not None and shortcut.label is not None:
                    section = section
                    name = controller.label
                    group = groups.get(name)
                    if group is None:
                        groups[name] = group = Gtk.ShortcutsGroup(title=name)
                        section.add_group(group)
                    group.add_shortcut(Gtk.ShortcutsShortcut(title=shortcut.label, accelerator=' '.join(shortcut.accels)))

        self.add_section(section_app)
        if groups_other:
            self.add_section(section_other)


class __unit__(unit.Unit):
    def __init__(self, manager):
        super().__init__(manager)

    def generate_actions(self):
        yield action.ActionInfo('BAD', self.BAD_cb, _("BAD"), ['<Control><Shift>b'])
        yield action.ActionInfo('help', self.help_cb, _("Help"), ['<Control>h', 'F1'])
        yield action.ActionInfo('about', self.about_cb, _("About"), ['<Control><Shift>h'])

    def BAD_cb(self, *args):
        focus = Gtk.Application.get_default().get_active_window().get_focus()
        print(focus)
        # for x in focus.observe_controllers():
        #     print(x)
        #     if isinstance(x, Gtk.ShortcutController):
        #         for sh in x:
        #             print(sh.get_trigger().to_string())

    def about_cb(self, *args):
        dialog = Gtk.AboutDialog(program_name=__program_name__, version=__version__, comments=__program_description__, copyright=__copyright__, license_type=__license_type__, logo_icon_name='face-cool-gampc', website=__website__)
        dialog.present()

    def help_cb(self, *args):
        app = Gtk.Application.get_default()
        window = app.get_active_window()
        ShortcutsWindow(window).present()
