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


from ..util import data
from ..util import db
from ..util import resource
from ..util import unit
from ..util.logger import logger
from ..components import songlistbase
from ..components import stream


class StreamDatabase(db.Database):
    def __init__(self, name, fields):
        self.fields = fields
        super().__init__(name)

    def setup_database(self):
        self.setup_table('streams', 'streamid INTEGER PRIMARY KEY', self.fields.basic_names)

    def get_streams(self):
        query = self.connection.cursor().execute('SELECT streamid,{} FROM streams'.format(','.join(self.fields.basic_names)))
        return map(lambda s: {name: s[i] for i, name in enumerate(['streamid'] + self.fields.basic_names)}, query)

    def save_streams(self, streams):
        with self.connection:
            self.connection.cursor().execute('DELETE FROM streams')
            for stream_ in streams:
                self.connection.cursor().execute('INSERT OR IGNORE INTO streams({}) VALUES({})'.format(','.join(self.fields.basic_names),
                                                                                                       ':' + ',:'.join(self.fields.basic_names)), stream_)


class __unit__(songlistbase.UnitMixinSongListBase, unit.Unit):
    COMPONENT_CLASS = stream.Stream

    def __init__(self, name, manager):
        super().__init__(name, manager)

        self.add_resources(
            'app.menu',
            resource.MenuPath('edit/component/stream'),
            resource.MenuAction('edit/component/stream', 'mod.stream-add', _("Add stream"), ),
            resource.MenuAction('edit/component/stream', 'mod.stream-modify', _("Modify stream"), ['F2']),
        )

        self.add_resources(
            'stream.context.menu',
            resource.MenuPath('stream'),
            resource.MenuAction('stream', 'mod.stream-add', _("Add stream")),
            resource.MenuAction('stream', 'mod.stream-modify', _("Modify stream")),
        )

        self.fields = data.FieldFamily(self.config.fields)
        self.fields.register_field(data.Field('Name', _("Name")))
        self.fields.register_field(data.Field('file', _("URL")))
        self.fields.register_field(data.Field('Comment', _("Comment")))

        self.db = StreamDatabase(self.name, self.fields)

        self.config.edit_dialog_size._get(default=[500, 500])

        self.unit_server.add_current_song_hook(self.current_song_hook)

    def shutdown(self):
        self.unit_server.remove_current_song_hook(self.current_song_hook)
        super().shutdown()

    def current_song_hook(self, song):
        if 'file' not in song or 'Title' not in song:
            return
        url = song['file']
        if not url.startswith('http://') and not url.startswith('https://'):
            return
        orig_title = title = song['Title']
        artist = song.get('Artist')
        performer = song.get('Performer')
        name = song.get('Name')
        if artist is None and ' - ' in title:
            artist, title = title.split(' - ', 1)
        if performer is None and ' & ' in artist:
            artist, performer = artist.split(' & ', 1)
        if name is not None:
            title += f' [{name}]'
        song.update(Title=title, Artist=artist, Performer=performer)

        logger.info(orig_title)
