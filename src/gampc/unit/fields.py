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


import urllib
import os

from gi.repository import GLib

from ..util import field
from ..util import misc
from ..util import unit

from . import mixins


class __unit__(mixins.UnitConfigMixin, unit.Unit):
    def __init__(self, manager):
        super().__init__(manager)

        self.config.music_dir._get(default=GLib.get_user_special_dir(GLib.USER_DIRECTORY_MUSIC))

        self.fields = field.FieldFamily(self.config)
        self.fields.register_field(field.Field('Album', _("Album")))
        self.fields.register_field(field.Field('AlbumArtist', _("Album artist")))
        self.fields.register_field(field.Field('Artist', _("Artist")))
        self.fields.register_field(field.Field('Composer', _("Composer")))
        self.fields.register_field(field.Field('Date', _("Date")))
        self.fields.register_field(field.Field('Disc', _("Disc")))
        self.fields.register_field(field.Field('file', _("File")))
        self.fields.register_field(field.Field('Genre', _("Genre")))
        self.fields.register_field(field.Field('Last_Modified', _("Last modified")))
        self.fields.register_field(field.Field('Performer', _("Performer")))
        self.fields.register_field(field.Field('Time', _("Seconds"), visible=False))
        self.fields.register_field(field.Field('FormattedTime', _("Duration"), get_value=lambda song: misc.format_time(song['Time']) if 'Time' in song else ''))
        # self.fields.register_field(field.Field('Title', _("Title")))
        self.fields.register_field(field.Field('Title', _("Title (partial)")))
        self.fields.register_field(field.Field('FullTitle', _("Title"), get_value=self.song_title))
        self.fields.register_field(field.Field('Track', _("Track")))
        self.fields.register_field(field.FieldWithTable(
            'Extension', _("Extension"),
            table=[
                [
                    'file',
                    '^http://',
                    ''
                ],
                [
                    'file',
                    '\\.([^.]*)$',
                    '\\1'
                ]
            ]))
        self.fields.register_field(field.FieldWithTable(
            'agenre', visible=False,
            table=[
                [
                    'Genre',
                    '[Mm]ilong',
                    'b milonga'
                ],
                [
                    'Genre',
                    '[Cc]andombe',
                    'b milonga'
                ],
                [
                    'Genre',
                    '[Tt]ango|Canci[oó]n',
                    'a tango'
                ],
                [
                    'Genre',
                    '[Vv]als',
                    'c vals'
                ],
                [
                    'Genre',
                    '[Ff]ox ?trot',
                    'd fox'
                ],
                [
                    'Genre',
                    '[Pp]aso ?doble',
                    'e paso'
                ],
                [
                    'Genre',
                    'Ranchera',
                    'f ranchera'
                ],
                [
                    None,
                    None,
                    'z'
                ]
            ]))
        self.fields.register_field(field.FieldWithTable(
            'ArtistSortName', visible=False,
            table=[
                [
                    'Artist',
                    '(La Típica Sanata|Otros Aires|.* Orquesta)',
                    '\\1'
                ],
                [
                    'Artist',
                    '^(.* Tango)$',
                    '\\1'
                ],
                [
                    'Artist',
                    '(.*), dir\\. (.*) ([^ ]+)',
                    '\\3, \\2 (\\1)'
                ],
                [
                    'Artist',
                    '(Orquesta Típica|Dúo|Cuarteto|Sexteto) (.*)',
                    '\\2, \\1'
                ],
                [
                    'Artist',
                    '(.*) ((?:Di|De) *[^ ]+)',
                    '\\2, \\1'
                ],
                [
                    'Artist',
                    '(.*) ([^ ]+)',
                    '\\2, \\1'
                ],
                [
                    'Artist',
                    '(.*)',
                    '\\1'
                ]
            ]))
        performer_last_name = field.FieldWithTable(
            'PerformerLastName', visible=False,
            table=[
                [
                    'Performer',
                    '^(.*) ((?:Di|De|Del) *[^ ]+)$',
                    '\\2'
                ],
                [
                    'Performer',
                    '^(.*) ([^ ]+)$',
                    '\\2'
                ],
                [
                    'Performer',
                    '^(.*)$',
                    '\\1'
                ]
            ])
        self.fields.register_field(field.Field(
            'PerformersLastNames', visible=False,
            get_value=lambda song: ', '.join(performer_last_name.get_value({'Performer': name}) for name in song.get('Performer').split(', ')) if song.get('Performer') else None))

    # try:
    #     import mutagen
    # except:
    #     mutagen = None

    @staticmethod
    def song_title(song):
        title = song.get('Title') or song.get('Name', '')
        filename = song.get('file', '')
        url = urllib.parse.urlparse(filename)
        if url.scheme:
            url_basename = os.path.basename(url.path)
            title = '{0} [{1}]'.format(title, url_basename) if title else url_basename
        return title

    # def get_mutagen_file(self, song):
    #     return None
    #     if self.mutagen is None:
    #         return None
    #     try:
    #         return self.mutagen.File(song['_gfile'].get_path())
    #     except:
    #         return None

    # @staticmethod
    # def get_mutagen_bitrate(song):
    #     if '_mutagen' not in song:
    #         return None
    #     try:
    #         return str(song['_mutagen'].info.bitrate // 1000)
    #     except:
    #         if song['file'].endswith('.flac'):
    #             return 'FLAC'
    #         else:
    #             return '???'
