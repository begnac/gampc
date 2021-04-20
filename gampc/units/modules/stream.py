# coding: utf-8
#
# Graphical Asynchronous Music Player Client
#
# Copyright (C) 2020 Itaï BEN YAACOV
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


from gampc import data
from gampc.util import ssde
from gampc.util import db
from gampc.util import resource
from gampc.util import recordlist
from gampc.util import module


class Stream(recordlist.RecordListWithEditDelNew):
    title = _("Internet Streams")
    name = 'stream'
    key = '4'

    DND_TARGET = 'GAMPC_STREAMS'

    def __init__(self, unit):
        self.fields = unit.fields

        super().__init__(unit)

        self.actions.add_action(resource.Action('stream-add', self.action_add_cb))
        self.actions.add_action(resource.Action('stream-modify', self.action_modify_cb))

        self.signal_handler_connect(self.unit.unit_server.ampd_server_properties, 'notify::current-song', self.notify_current_song_cb)

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
        value = self.unit.ssde_struct.edit(self.win, size=self.config[self.unit.unit_config.CONFIG_EDIT_DIALOG_SIZE], scrolled=True)
        if value:
            self.add_record(value)

    def action_modify_cb(self, action, parameter):
        path, column = self.treeview.get_cursor()
        if path is None:
            return
        i = self.store.get_iter(path)
        value = self.store.get_record(i).get_data()
        value = self.unit.ssde_struct.edit(self.win, value, size=self.config[self.unit.unit_config.CONFIG_EDIT_DIALOG_SIZE], scrolled=True)
        if value is not None:
            self.modify_record(i, value)

    def notify_current_song_cb(self, *args):
        self.treeview.queue_draw()

    def set_modified(self):
        pass

    def data_func(self, column, renderer, store, i, j):
        super().data_func(column, renderer, store, i, j)
        if self.unit.unit_server.ampd_server_properties.state != 'stop' and store.get_record(i).file == self.unit.unit_server.ampd_server_properties.current_song.get('file'):
            renderer.set_property('font', 'italic bold')
            bg = self._mix_colors(1, 1, 1)
            renderer.set_property('background-rgba', bg)
        else:
            renderer.set_property('font', None)


class StreamDatabase(db.Database):
    def __init__(self, fields):
        self.fields = fields
        super().__init__(Stream.name)

    def setup_database(self):
        self.setup_table('streams', 'streamid INTEGER PRIMARY KEY', self.fields.basic_names)

    def get_streams(self):
        query = self.connection.cursor().execute('SELECT streamid,{} FROM streams'.format(','.join(self.fields.basic_names)))
        return map(lambda s: {name: s[i] for i, name in enumerate(['streamid'] + self.fields.basic_names)}, query)

    def save_streams(self, streams):
        with self.connection:
            self.connection.cursor().execute('DELETE FROM streams')
            for stream in streams:
                self.connection.cursor().execute('INSERT OR IGNORE INTO streams({}) VALUES({})'.format(','.join(self.fields.basic_names),
                                                                                                       ':' + ',:'.join(self.fields.basic_names)), stream)


class __unit__(module.UnitWithModule):
    REQUIRED_UNITS = ['misc']
    MODULE_CLASS = Stream

    def __init__(self, name, manager):
        super().__init__(name, manager)

        self.setup_menu('stream', 'context')

        self.new_resource_provider('app.menu').add_resources(
            resource.MenuPath('edit/module/stream'),
        )

        self.new_resource_provider('app.user-action').add_resources(
            resource.UserAction('mod.stream-add', _("Add stream"), 'edit/module/stream'),
            resource.UserAction('mod.stream-modify', _("Modify stream"), 'edit/module/stream', ['F2']),
        )

        self.new_resource_provider('stream.context.menu').add_resources(
            resource.MenuPath('stream'),
            resource.MenuAction('stream/mod.stream-add', _("Add stream")),
            resource.MenuAction('stream/mod.stream-modify', _("Modify stream")),
        )

        self.fields = data.FieldFamily(self.config.fields)
        self.fields.register_field(data.Field('Name', _("Name")))
        self.fields.register_field(data.Field('file', _("URL")))
        self.fields.register_field(data.Field('Comment', _("Comment")))

        self.db = StreamDatabase(self.fields)

        self.config.access(self.unit_config.CONFIG_EDIT_DIALOG_SIZE, [500, 500])
        self.ssde_struct = ssde.Dict(
            label=_("Internet stream"),
            substructs=[
                ssde.Text(label=_("Name"), name='Name', validator=bool),
                ssde.Text(label=_("URL"), name='file', default='http://'),
                ssde.Text(label=_("Comment"), name='Comment'),
            ])
