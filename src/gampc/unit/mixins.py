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

import ampd

from ..util import action


class UnitCssMixin:
    CSS = ''

    def __init__(self, *args):
        super().__init__(*args)
        self.css_provider = Gtk.CssProvider()
        self.css_provider.load_from_string(self.CSS)
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


class UnitItemListMixin:
    def new_widget(self):
        component = super().new_widget()
        component.connect_clean(self.view.item_view, 'activate', self.view_activate_cb)
        return component

    @ampd.task
    async def view_activate_cb(self, view, position):
        if self.unit.unit_persistent.protect_active:
            return
        filename = self.view.item_selection_model[position].get_key()
        items = await self.ampd.playlistfind('file', filename)
        if items:
            item_id = sorted(items, key=lambda item: item['Pos'])[0]['Id']
        else:
            item_id = await self.ampd.addid(filename)
        await self.ampd.playid(item_id)


# class UnitComponentMixin(UnitConfigMixin, UnitServerMixin):
#     def __init__(self, *args, menus=[]):
#         super().__init__(*args)
#         self.require('component').register_component(self.name, self.title, self.key, self.new_widget)

#     def cleanup(self):
#         self.unit_component.unregister_component(self.name)
#         super().cleanup()

#     def new_widget(self):
#         return self.COMPONENT_CLASS(self)


# class UnitPanedComponentMixin(UnitComponentMixin):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.config.pane_separator._get(default=100)


class UnitComponentQueueActionMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config.pane_separator._get(default=100)

    @ampd.task
    async def view_activate_cb(self, item_view, position):
        if self.unit_persistent.protect_active:
            return
        filename = item_view.get_model()[position].get_key()
        items = await self.ampd.playlistfind('file', filename)
        if items:
            item_id = sorted(items, key=lambda item: item['Pos'])[0]['Id']
        else:
            item_id = await self.ampd.addid(filename)
        await self.ampd.playid(item_id)

    def generate_global_queue_actions(self, view):
        yield action.ActionInfo('queue-add-high-priority', self.action_queue_add_cb, _("Add to play queue with high priority"), arg=False, arg_format='b', activate_args=(view,))
        yield action.ActionInfo('queue-add', self.action_queue_add_cb, _("Add to play queue"), arg=False, arg_format='b', activate_args=(view,))
        yield action.ActionInfo('queue-replace', self.action_queue_add_cb, _("Replace play queue"), arg=False, arg_format='b', dangerous=True, activate_args=(view,))

    def generate_local_queue_actions(self, view):
        for action_ in self.generate_global_queue_actions(view):
            yield action_.derive(action_.label, arg=True)

    @ampd.task
    async def action_queue_add_cb(self, action, parameter, view):
        filenames = view.get_filenames(parameter.unpack())
        replace = '-replace' in action.get_name()
        if replace:
            await self.ampd.clear()
        Ids = await self.ampd.command_list(self.ampd.addid(filename) for filename in filenames)
        if replace:
            await self.ampd.play()
        if '-high-priority' in action.get_name():
            await self.ampd.prioid(255, *Ids)
