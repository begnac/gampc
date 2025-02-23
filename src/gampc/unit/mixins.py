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


from gi.repository import GObject
from gi.repository import Gtk

import ampd

from ..util import action
from ..util import cleanup
from ..util import config
from ..util import misc


class UnitConfigMixin:
    def __init__(self, manager, _config):
        super().__init__(manager)
        self.config = config.load_json(self.name, _config)

    def cleanup(self):
        super().cleanup()
        config.save_json(self.name, self.config)


class UnitServerMixin(cleanup.CleanupBaseMixin):
    def __init__(self, manager):
        super().__init__(manager)

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


class ComponentWidget(cleanup.CleanupSignalMixin, Gtk.Box):
    subtitle = GObject.Property(type=str)

    def __init__(self, widget, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect('notify::subtitle', self.__class__.notify_subtitle_cb)
        self.connect('map', self.__class__.map_cb)
        self.append(widget)
        self.widget = widget
        self.add_cleanup_below(widget)

    # Should not be necessary !
    def cleanup(self):
        super().cleanup()
        self.remove(self.widget)
        del self.widget
        del self._cleanup_below

    def notify_subtitle_cb(self, pspec):
        window = self.get_root()
        if window is not None:
            window.set_subtitle(self.subtitle)

    def map_cb(self):
        self.get_root().set_subtitle(self.subtitle)

    def grab_focus(self):
        return self.get_first_child().grab_focus()


class UnitComponentMixin:
    def __init__(self, manager):
        super().__init__(manager)
        self.require('component').register_component(self.name, self.TITLE, self.KEY, self.factory)

    def cleanup(self):
        self.unit_component.unregister_component(self.name)
        super().cleanup()

    def factory(self):
        return ComponentWidget(self.new_widget(), subtitle=self.TITLE)


class UnitComponentTotalsMixin(UnitComponentMixin):
    def factory(self):
        component = super().factory()
        store = component.widget.totals_store
        component.widget.connect_clean(store, 'items-changed', self.totals_items_changed_cb, component, self.TITLE)
        self.totals_items_changed_cb(store, 0, 0, 0, component, self.TITLE)
        return component

    @staticmethod
    def totals_items_changed_cb(store, p, r, a, component, title):
        time = sum(int(item.get_field('Time', '0')) for item in store)
        component.subtitle = f'{title} [{store.get_n_items()} / {misc.format_time(time)}]'


class UnitComponentQueueActionMixin(UnitComponentMixin, UnitServerMixin):
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

    def generate_foreign_queue_actions(self, view, selection=True):
        yield action.ActionInfo('queue-add', self.action_queue_add_cb, _("Add to play queue"), arg=selection, arg_format='b', activate_args=(view,))
        yield action.ActionInfo('queue-replace', self.action_queue_add_cb, _("Replace play queue"), arg=selection, arg_format='b', dangerous=True, activate_args=(view,))
        yield action.ActionInfo('queue-add-high-priority', self.action_queue_add_cb, _("Add to play queue with high priority"), arg=selection, arg_format='b', activate_args=(view,))

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


class UnitComponentPlaylistActionMixin(UnitComponentMixin):
    def generate_foreign_playlist_actions(self, widget, selection=True):
        yield action.ActionInfo('playlist-saveas', self.manager.get_unit('playlist').action_playlist_saveas_cb, _("Save as playlist"), arg=selection, arg_format='b', activate_args=(widget,))


class UnitComponentTandaActionMixin(UnitComponentMixin):
    def generate_foreign_tanda_actions(self, widget):
        yield action.ActionInfo('tanda-define', self.manager.get_unit('tanda').action_tanda_define_cb, _("Define tanda"), activate_args=(widget,))
