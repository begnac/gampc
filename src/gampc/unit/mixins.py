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


class UnitItemListMixin:
    def new_component(self):
        component = super().new_component()
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
#         self.require('component').register_component(self.name, self.title, self.key, self.new_component)

#     def cleanup(self):
#         self.unit_component.unregister_component(self.name)
#         super().cleanup()

#     def new_component(self):
#         return self.COMPONENT_CLASS(self)


# class UnitPanedComponentMixin(UnitComponentMixin):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.config.pane_separator._get(default=100)


# class UnitComponentQueueActionMixin:
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.config.pane_separator._get(default=100)

#     def generate_global_queue_actions(self):
#         yield action.ActionInfo('queue-add-high-priority', self.action_queue_add_high_priority_cb, _("Add to play queue with high priority"), arg=False, arg_format='b')
#         yield action.ActionInfo('queue-add', self.action_queue_add_high_priority_cb, _("Add to play queue"), arg=False, arg_format='b')
#         yield action.ActionInfo('queue-replace', self.action_queue_add_high_priority_cb, _("Replace play queue"), arg=False, arg_format='b', dangerous=True)

#     def generate_local_queue_actions(self):
#         for action_ in self.generate_global_queue_actions():
#             yield action_.derive(arg=True)

#     @ampd.task
#     async def action_queue_add_replace_cb(self, action, parameter):
#         filenames = self.get_filenames(parameter.get_boolean())
#         replace = '-replace' in action.get_name()
#         if replace:
#             await self.ampd.clear()
#         print(await self.ampd.command_list(self.ampd.addid(filename) for filename in filenames))
#         if replace:
#             await self.ampd.play()

#     @ampd.task
#     async def action_queue_add_high_priority_cb(self, action, parameter):
#         filenames = self.get_filenames(parameter.get_boolean())
#         queue = {song['file']: song for song in await self.ampd.playlistinfo()}
#         Ids = []
#         for filename in filenames:
#             Ids.append(queue[filename]['Id'] if filename in queue else await self.ampd.addid(filename))
#         await self.ampd.prioid(255, *Ids)
