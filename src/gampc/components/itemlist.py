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


import ampd

from ..util import misc

from . import component


class ItemList(component.Component):
    def __init__(self, unit, view, *args, **kwargs):
        super().__init__(unit, *args, **kwargs)

        self.view = view
        self.view.item_view.add_css_class('itemlist')

        self.connect_clean(self.view.item_view, 'activate', self.view_activate_cb)

    def cleanup(self):
        self.widget.cleanup()
        del self.view
        super().cleanup()

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


class SongListTotalsMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect_clean(self.view.item_store, 'items-changed', self.set_totals)

    def set_totals(self, store, *args):
        time = sum(int(item.get_field('Time', '0')) for item in store)
        self.status = '{} / {}'.format(store.get_n_items(), misc.format_time(time))
