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


from ..util import field
from ..util import unit

from . import mixins


class __unit__(mixins.UnitConfigMixin, unit.Unit):
    def __init__(self, manager):
        super().__init__(manager,
                         field.get_fields_config())

        # self.config.music_dir._get(default=GLib.get_user_special_dir(GLib.USER_DIRECTORY_MUSIC))

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
        self.fields.register_field(field.Field('duration', visible=False))
        self.fields.register_field(field.Field('Duration', _("Duration")))
        self.fields.register_field(field.Field('Title', _("Title")))
        self.fields.register_field(field.Field('Track', _("Track")))
        self.fields.register_field(field.Field('Extension', _("Extension")))

    # try:
    #     import mutagen
    # except:
    #     mutagen = None

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
