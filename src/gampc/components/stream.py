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


from ..util import ssde
from ..util import resource
from . import songlistbase


class Stream(songlistbase.SongListBaseWithEditDelNew):
    use_resources = ['songlistbase']
    DND_TARGET = 'GAMPC_STREAM'

    def __init__(self, unit):
        self.fields = unit.fields

        super().__init__(unit)

        self.actions.add_action(resource.Action('add', self.action_add_cb))
        self.actions.add_action(resource.Action('modify', self.action_modify_cb))

        self.ssde_struct = ssde.Dict(
            label=_("Internet stream"),
            substructs=[
                ssde.Text(label=_("Name"), name='Name', validator=bool),
                ssde.Text(label=_("URL"), name='file', default='http://'),
                ssde.Text(label=_("Comment"), name='Comment'),
            ])

        self.signal_handler_connect(self.unit.unit_server, 'notify::current-song', self.notify_current_song_cb)

        self.load_streams()

    def load_streams(self):
        streams = self.unit.db.get_streams()
        self.store.set_rows(streams)

    def action_save_cb(self, action, parameter):
        streams = [stream.get_data() for i, p, stream in self.store if stream._status != self.RECORD_DELETED]
        self.unit.db.save_streams(streams)
        self.load_streams()

    def action_reset_cb(self, action, parameter):
        self.load_streams()

    def action_add_cb(self, action, parameter):
        value = self.unit.ssde_struct.edit(self.win, size=self.config.edit_dialog_size._get(), scrolled=True)
        if value:
            self.add_record(value)

    def action_modify_cb(self, action, parameter):
        path, column = self.treeview.get_cursor()
        if path is None:
            return
        i = self.store.get_iter(path)
        value = self.store.get_record(i).get_data()
        value = self.ssde_struct.edit(self.win, value, size=self.configself.config.edit_dialog_size._get(), scrolled=True)
        if value is not None:
            self.modify_record(i, value)

    def notify_current_song_cb(self, *args):
        self.treeview.queue_draw()

    def set_modified(self):
        pass

    def data_func(self, column, renderer, store, i, j):
        super().data_func(column, renderer, store, i, j)
        if self.unit.unit_server.ampd_server_properties.state != 'stop' and store.get_record(i).file == self.unit.unit_server.current_song.get('file'):
            renderer.set_property('font', 'italic bold')
            bg = self._mix_colors(1, 1, 1)
            renderer.set_property('background-rgba', bg)
        else:
            renderer.set_property('font', None)
