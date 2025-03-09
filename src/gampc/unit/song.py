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


from ..util import unit

from ..view import field

from . import mixins


class __unit__(mixins.UnitConfigMixin, unit.Unit):
    def __init__(self, manager):
        super().__init__(manager, field.get_fields_config())

        fields = {
            'Album': dict(title=_("Album")),
            'AlbumArtist': dict(title=_("Album artist")),
            'Artist': dict(title=_("Artist")),
            'Composer': dict(title=_("Composer")),
            'Date': dict(title=_("Date")),
            'Disc': dict(title=_("Disc")),
            'file': dict(title=_("File")),
            'Genre': dict(title=_("Genre")),
            'Last_Modified': dict(title=_("Last modified")),
            'Performer': dict(title=_("Performer")),
            'Track': dict(title=_("Track")),
            'Title': dict(title=_("Title")),
            'Duration': dict(title=_("Duration")),
            'Extension': dict(title=_("Extension")),
        }

        self.fields = field.FieldsInfo(self.config, fields)

        # self.config.music_dir._get(default=GLib.get_user_special_dir(GLib.USER_DIRECTORY_MUSIC))

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
