# coding: utf-8
#
# Graphical Asynchronous Music Player Client
#
# Copyright (C) 2015 Itaï BEN YAACOV
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


from gi.repository import GLib
from gi.repository import Gio
from gi.repository import Gtk

import urllib.parse
import os.path

from gampc import data
from gampc.util import ssde
from gampc.util import resource
from gampc.util import recordlist
from gampc.util import module
from gampc.util import unit


class SongList(recordlist.RecordList):
    use_resources = ['songlist']
    DND_TARGET = 'GAMPC_SONGS'

    def __init__(self, unit):
        self.fields = unit.unit_songlist.fields
        super().__init__(unit)


class SongListWithTotals(SongList):
    def set_records(self, songs, set_fields=True):
        super().set_records(songs, set_fields)
        time = sum(int(song.get('Time', '0')) for song in songs)
        self.status = '{} / {}'.format(len(songs), data.format_time(time))


class SongListWithEditDel(SongList, recordlist.RecordListWithEditDel):
    pass


class SongListWithAdd(SongList, recordlist.RecordListWithAdd):
    def __init__(self, unit):
        super().__init__(unit)
        self.actions.add_action(resource.Action('add-separator', self.action_add_separator_cb))
        self.actions.add_action(resource.Action('add-url', self.action_add_url_cb))

    def action_add_separator_cb(self, action, parameter):
        self.add_record(dict(self.unit.unit_server.separator_song))

    def action_add_url_cb(self, action, parameter):
        struct = ssde.Text(label=_("URL or filename to add"), default='http://')
        url = struct.edit(self.win)
        if url:
            self.add_record(dict(file=url))


class SongListWithEditDelNew(SongListWithAdd, recordlist.RecordListWithEditDelNew):
    pass


class SongListWithEditDelFile(SongListWithEditDel):
    def records_set_fields(self, songs):
        for song in songs:
            gfile = Gio.File.new_for_path(GLib.build_filenamev([self.unit.unit_songlist.config.music_dir, song['file']]))
            if gfile.query_exists():
                song['_gfile'] = gfile
            else:
                song['_status'] = self.RECORD_UNDEFINED
        super().records_set_fields(songs)

    def action_save_cb(self, action, parameter):
        self.save_files(song for i, p, song in self.store)

    def action_save_selected_cb(self, action, parameter):
        songs, refs = self.treeview.get_selection_rows()

    def save_files(self, songs):
        deleted = [song for song in songs if song._status == self.RECORD_DELETED]
        if deleted:
            dialog = Gtk.Dialog(parent=self.win, title=_("Move to trash"))
            dialog.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
            dialog.add_button(_("_OK"), Gtk.ResponseType.OK)
            dialog.get_content_area().add(Gtk.Label(label='\n\t'.join([_("Move these files to the trash?")] + [song.file for song in deleted]), visible=True))
            reply = dialog.run()
            dialog.destroy()
            if reply != Gtk.ResponseType.OK:
                return
            for song in deleted:
                song._gfile.trash()
                song._status = self.RECORD_UNDEFINED

    def set_modified(self):
        self.status = _("modified")

    def set_records(self, songs, set_fields=True):
        self.status = None
        super().set_records(songs, set_fields)


class UnitWithSongList(module.UnitWithModule):
    def __init__(self, name, manager):
        self.REQUIRED_UNITS = ['misc', 'songlist'] + self.REQUIRED_UNITS
        super().__init__(name, manager)
        self.setup_menu(self.MODULE_CLASS.name, 'context', self.MODULE_CLASS.use_resources)


class UnitWithPanedSongList(UnitWithSongList):
    def __init__(self, name, manager):
        super().__init__(name, manager)
        self.setup_menu(self.MODULE_CLASS.name, 'left-context', self.MODULE_CLASS.use_resources)


class __unit__(unit.UnitWithConfig):
    def __init__(self, name, manager):
        super().__init__(name, manager)

        actions = [
            resource.UserAction('mod.cut', _("Cut"), 'edit/module/base', ['<Control>x'], accels_fragile=True),
            resource.UserAction('mod.copy', _("Copy"), 'edit/module/base', ['<Control>c'], accels_fragile=True),
            resource.UserAction('mod.paste', _("Paste"), 'edit/module/base', ['<Control>v'], accels_fragile=True),
            resource.UserAction('mod.paste-before', _("Paste before"), 'edit/module/base', ['<Control>b']),
            resource.UserAction('mod.delete', _("Delete"), 'edit/module/base', ['Delete'], accels_fragile=True),
            resource.UserAction('mod.undelete', _("Undelete"), 'edit/module/base', ['<Alt>Delete'], accels_fragile=True),
            resource.UserAction('mod.add-separator', _("Add separator"), 'edit/module/special'),
            resource.UserAction('mod.add-url', _("Add URL or filename"), 'edit/module/special'),
        ]

        menus = [
            resource.MenuPath('edit/module/base'),
            resource.MenuPath('edit/module/special'),
        ]

        self.new_resource_provider('app.menu').add_resources(*menus)

        self.new_resource_provider('app.user-action').add_resources(
            resource.UserAction('mod.save', _("Save"), 'edit/global', ['<Control>s']),
            resource.UserAction('mod.reset', _("Reset"), 'edit/global', ['<Control>r']),
            resource.UserAction('mod.filter', _("Filter"), 'edit/global', ['<Control><Shift>f']),
            *actions,
        )

        self.new_resource_provider('songlist.context.menu').add_resources(
            resource.MenuPath('action'),
            resource.MenuPath('edit'),
            resource.MenuPath('edit/module'),
            *menus,
            resource.MenuPath('other'),
        )

        self.new_resource_provider('songlist.context.user-action').add_resources(*actions)

        self.new_resource_provider('songlist.left-context.menu').add_resources(
            resource.MenuPath('action'),
            resource.MenuPath('edit'),
            resource.MenuPath('other'),
        )

        self.config.access('music-dir', GLib.get_user_special_dir(GLib.USER_DIRECTORY_MUSIC))

        self.fields = data.FieldFamily(self.config.fields)
        self.fields.register_field(data.Field('Album', _("Album")))
        self.fields.register_field(data.Field('AlbumArtist', _("Album artist")))
        self.fields.register_field(data.Field('Artist', _("Artist")))
        self.fields.register_field(data.Field('Composer', _("Composer")))
        self.fields.register_field(data.Field('Date', _("Date")))
        self.fields.register_field(data.Field('Disc', _("Disc")))
        self.fields.register_field(data.Field('file', _("File")))
        self.fields.register_field(data.Field('Genre', _("Genre")))
        self.fields.register_field(data.Field('Last_Modified', _("Last modified")))
        self.fields.register_field(data.Field('Performer', _("Performer")))
        self.fields.register_field(data.Field('Time', _("Seconds"), visible=False))
        self.fields.register_field(data.Field('FormattedTime', _("Duration"), get_value=lambda song: data.format_time(song['Time']) if 'Time' in song else ''))
        self.fields.register_field(data.Field('Title', _("Title (partial)")))
        self.fields.register_field(data.Field('FullTitle', _("Title"), get_value=self.song_title))
        self.fields.register_field(data.Field('Track', _("Track")))
        self.fields.register_field(data.FieldWithTable(
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
        self.fields.register_field(data.FieldWithTable(
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
        self.fields.register_field(data.FieldWithTable(
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
                    '(.*), dir\. (.*) ([^ ]+)',
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
        performer_last_name = data.FieldWithTable(
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
        self.fields.register_field(data.Field(
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
