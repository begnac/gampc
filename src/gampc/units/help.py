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

import xml.sax.saxutils

from ..util import resource
from ..util import unit

from .. import __program_name__, __version__, __program_description__, __copyright__, __license_type__, __website__


def shortcuts_interface(resources):
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

    groups = [xml_group(**group) for group in groups]
    section = xml_object('GtkShortcutsSection', {'section-name': 'section', 'title': _("Shortcuts")}, groups)
    window = xml_object('GtkShortcutsWindow', {'modal': 'true'}, [section], attrs={'id': 'window'})
    yield from xml_interface([window])


def xml_group(name, title, items):
    shortcuts = [xml_shortcut(item.label.replace('_', ''), item.accels) for item in items]
    return xml_object('GtkShortcutsGroup', {'name': name, 'title': title}, shortcuts)


def xml_shortcut(title, accels):
    return xml_object('GtkShortcutsShortcut', {'title': title, 'accelerator': ' '.join(accels)})


def xml_object(class_, props, children=[], *, attrs={}):
    attributes = ' '.join(f'{name}="{value}"' for name, value in [('class', class_)] + list(attrs.items()))
    yield f'<object {attributes}>'
    for name, value in props.items():
        yield f'<property name="{name}">{xml.sax.saxutils.escape(value)}</property>'
    for child in children:
        yield '<child>'
        yield from child
        yield '</child>'
    yield '</object>'


def xml_interface(objects):
    yield '<interface>'
    for obj in objects:
        yield from obj
    yield '</interface>'


class __unit__(unit.UnitServerMixin, unit.Unit):
    def __init__(self, name, manager):
        super().__init__(name, manager)

        self.aggregator = resource.MenuAggregator(['app.menu'])
        self.manager.add_aggregator(self.aggregator)

        self.add_resources(
            'app.action',
            resource.ActionModel('BAD', self.BAD_cb),
            resource.ActionModel('help', self.help_cb),
            resource.ActionModel('about', self.about_cb),
        )

        self.add_resources(
            'app.menu',
            resource.MenuAction('help', 'app.BAD', _("BAD"), ['<Control><Shift>b']),
            resource.MenuAction('help', 'app.help', _("Help"), ['<Control>h', 'F1']),
            resource.MenuAction('help', 'app.about', _("About"), ['<Control><Shift>h']),
        )

    def BAD_cb(self, *args):
        print(self.get_active_window().get_focus())

    def about_cb(self, *args):
        dialog = Gtk.AboutDialog(program_name=__program_name__, version=__version__, comments=__program_description__, copyright=__copyright__, license_type=__license_type__, logo_icon_name='face-cool-gampc', website=__website__)
        dialog.present()

    def help_cb(self, *args):
        builder = Gtk.Builder.new_from_string(''.join(shortcuts_interface(self.aggregator.get_all_resources())), -1)
        window = builder.get_object('window')
        window.present()
