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

from .. import util
from .. import ui

from . import itemlist


class Stream(itemlist.ItemListEditStackMixin, itemlist.ItemList):
    use_resources = ['itemlist']
    DND_TARGET = 'GAMPC_STREAM'

    def __init__(self, unit):
        self.fields = unit.fields

        super().__init__(unit, widget_factory=self.widget_factory)
        self.widget.item_view.add_css_class('stream')

        self.actions.add_action(util.resource.Action('add', self.action_add_cb))
        self.actions.add_action(util.resource.Action('modify', self.action_modify_cb))

        # self.ssde_struct = ssde.Dict(
        #     label=_("Internet stream"),
        #     substructs=[
        #         ssde.Text(label=_("Name"), name='Name', validator=bool),
        #         ssde.Text(label=_("URL"), name='file', default='http://'),
        #         ssde.Text(label=_("Comment"), name='Comment'),
        #     ])

        self.signal_handler_connect(self.unit.unit_server, 'notify::current-song', self.notify_current_song_cb)
        # self.widget.record_display_hooks.append(self.record_current_song_hook)

        self.load_streams()

    def splice_items(self, pos, remove, add):
        add = list(add)
        super().splice_items(pos, remove, add)
        for item in self.view.item_store[pos:pos + len(add)]:
            item.connect('changed', self.stream_changed_cb)

    def widget_factory(self):
        return ui.editable.EditableLabel(always_editable=False, unit_misc=self.unit.unit_misc)

    def stream_changed_cb(self, *args):
        print(args)

    def item_factory(self):
        return util.item.ItemWithDict()

    # def record_current_song_hook(self, label, record):
    #     if self.unit.unit_server.ampd_server_properties.state != 'stop' and record.file == self.unit.unit_server.ampd_server_properties.current_song.get('file'):
    #         label.get_parent().add_css_class('playing')

    def load_streams(self):
        streams = self.unit.db.get_streams()
        # self.set_songs(streams)
        self.set_edit_stack(util.editstack.EditStack(streams))

    def action_save_cb(self, action, parameter):
        raise NotImplementedError
    #     streams = [stream.get_data() for i, p, stream in self.view.record_store if stream._status != self.RECORD_DELETED]
    #     self.unit.db.save_streams(streams)
    #     self.load_streams()

    def action_reset_cb(self, action, parameter):
        self.load_streams()

    def action_add_cb(self, action, parameter):
        value = self.unit.ssde_struct.edit(self.get_window(), size=self.config.edit_dialog_size._get(), scrolled=True)
        if value:
            self.add_record(value)

    @ampd.task
    async def action_modify_cb(self, action, parameter):
        pos = self.view.get_current_position()
        if pos is None:
            return
        record = self.view.record_selection[pos]
        value = await self.ssde_struct.edit(self.get_window(), record.get_data(), size=self.config.edit_dialog_size._get(), scrolled=True)
        if value is None:
            return
        record.set_data(value)
        record._modified = True
        record.emit('changed')

    def notify_current_song_cb(self, *args):
        for item in self.view.item_store:
            item.rebind()
