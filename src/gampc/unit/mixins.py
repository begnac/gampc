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


from gi.repository import Gdk
from gi.repository import Gtk


class UnitCssMixin:
    def __init__(self, *args):
        super().__init__(*args)
        self.css_provider = Gtk.CssProvider()
        self.css_provider.load_from_data(self.CSS, -1)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def cleanup(self):
        Gtk.StyleContext.remove_provider_for_display(Gdk.Display.get_default(), self.css_provider)
        super().cleanup()


class UnitConfigMixin:
    def __init__(self, *args):
        super().__init__(*args)
        self.require('config')
        self.config = self.unit_config.load_config(self.name)


class UnitServerMixin:
    def __init__(self, *args):
        super().__init__(*args)

        self.require('server')
        self.ampd = self.unit_server.ampd_client.executor.sub_executor()
        self.connect_clean(self.unit_server.ampd_client, 'client-connected', self.client_connected_cb)
        if self.ampd.get_is_connected():
            self.client_connected_cb(self.unit_server.ampd_client)

    def cleanup(self):
        self.ampd.close()
        super().cleanup()

    @staticmethod
    def client_connected_cb(client):
        pass


class UnitComponentMixin(UnitConfigMixin, UnitServerMixin):
    def __init__(self, *args, menus=[]):
        super().__init__(*args)
        self.require('component').register_component(self.name, self.title, self.key, self.new_component)

        # for menu in menus:
        #     self.setup_menu(self.name, menu, self.COMPONENT_CLASS.use_resources)

    def cleanup(self):
        # for aggregator in self.menu_aggregators.values():
        #     self.manager.remove_aggregator(aggregator)
        # del self.menu_aggregators
        self.unit_component.unregister_component(self.name)
        super().cleanup()

    def new_component(self):
        return self.COMPONENT_CLASS(self)

    # def setup_menu(self, name, kind, providers=[]):
    #     aggregator = util.resource.MenuAggregator([f'{provider}.{kind}.menu' for provider in [name] + providers])
    #     self.manager.add_aggregator(aggregator)
    #     self.menu_aggregators[f'{name}.{kind}'] = aggregator


class UnitPanedComponentMixin(UnitComponentMixin, UnitConfigMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config.pane_separator._get(default=100)
