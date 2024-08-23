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

from ..util import resource
from ..util import unit
from ..ui import shortcut

from .. import __program_name__, __version__, __program_description__, __copyright__, __license_type__, __website__


def iterate_children(widget):
    yield widget
    for child in widget:
        yield from iterate_children(child)


class ShortcutsGroup(Gtk.ShortcutsGroup):
    def __init__(self, items, **kwargs):
        super().__init__(**kwargs)
        for item in items:
            self.add_shortcut(Gtk.ShortcutsShortcut(title=item.label.replace('_', ''), accelerator=' '.join(item.accels)))


class ShortcutsWindow(Gtk.ShortcutsWindow):
    def __init__(self, resources, window):
        super().__init__(modal=True)
        section = Gtk.ShortcutsSection()

        for child in iterate_children(window):
            for controller in child.observe_controllers():
                if isinstance(controller, shortcut.ShortcutController):
                    group = Gtk.ShortcutsGroup(title=controller.title)
                    for accel in controller.accels:
                        group.add_shortcut(Gtk.ShortcutsShortcut(title=accel.title.replace('_', ''), accelerator=' '.join(accel.accels)))
                    section.add_group(group)

        groups = []
        groups_by_name = {}
        for menu_item in resources:
            path_components = menu_item.path.split('/', 1)
            name = path_components[0]
            if len(path_components) == 1:
                group = {'name': name, 'title': menu_item.label.replace('_', ''), 'items': []}
                groups.append(group)
                groups_by_name[name] = group
            elif isinstance(menu_item, resource.MenuAction) and menu_item.accels:
                groups_by_name[name]['items'].append(menu_item)

        for group in groups:
            section.add_group(ShortcutsGroup(**group))
        self.add_section(section)


class __unit__(unit.UnitServerMixin, unit.Unit):
    def __init__(self, name, manager):
        super().__init__(name, manager)

        self.aggregator = resource.MenuAggregator(['app.menu'])
        self.manager.add_aggregator(self.aggregator)

        self.add_resources(
            'app.action',
            # resource.ActionModel('BAD', self.BAD_cb),
            resource.ActionModel('help', self.help_cb),
            resource.ActionModel('about', self.about_cb),
        )

        self.add_resources(
            'app.menu',
            # resource.MenuAction('help', 'app.BAD', _("BAD"), ['<Control><Shift>b']),
            resource.MenuAction('help', 'app.help', _("Help"), ['<Control>h', 'F1']),
            resource.MenuAction('help', 'app.about', _("About"), ['<Control><Shift>h']),
        )

    # def BAD_cb(self, *args):
    #     print(self.get_active_window().get_focus())

    def about_cb(self, *args):
        dialog = Gtk.AboutDialog(program_name=__program_name__, version=__version__, comments=__program_description__, copyright=__copyright__, license_type=__license_type__, logo_icon_name='face-cool-gampc', website=__website__)
        dialog.present()

    def help_cb(self, *args):
        window = Gtk.Application.get_default().get_active_window()
        ShortcutsWindow(self.aggregator.get_all_resources(), window).present()
