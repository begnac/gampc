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


from gi.repository import GLib
from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import Gtk

import ast

from ..util import ssde
from ..util import record
from ..util import resource
from ..util.misc import format_time

from . import songlistbase
from . import component


class SongList(songlistbase.SongListBase):
    use_resources = ['songlistbase', 'songlist']
    DND_TARGET = 'GAMPC_SONG'

    def __init__(self, unit, *args, **kwargs):
        self.fields = unit.unit_songlist.fields
        super().__init__(unit, *args, **kwargs)
        self.songlist_actions = self.add_actions_provider('songlist')
        # self.songlist_actions.add_action(resource.Action('delete-file', self.action_delete_file_cb))

    def shutdown(self):
        del self.songlist_actions
        super().shutdown()

    @staticmethod
    def content_from_records(records):
        return Gdk.ContentProvider.new_for_value(repr([record.get_data_clean() for record in records]))

    @staticmethod
    def data_from_raw(raw):
        try:
            songs = ast.literal_eval(raw)
            if isinstance(songs, list) and all(isinstance(song, dict) and all(isinstance(key, str) and isinstance(value, str) for key, value in song.items()) for song in songs):
                return songs
        except Exception:
            pass

    def records_from_data(self, songs):
        self.set_extra_fields(songs)
        return list(map(record.Record, songs))

    def get_filenames(self, selection):
        return self.view.get_filenames(selection)

    # def records_set_fields(self, songs):
    #     for song in songs:
    #         gfile = Gio.File.new_for_path(GLib.build_filenamev([self.unit.unit_songlist.config.music_dir._get(), song['file']]))
    #         if gfile.query_exists():
    #             song['_gfile'] = gfile
    #         else:
    #             song['_status'] = self.RECORD_MODIFIED
    #     super().records_set_fields(songs)

    # def action_delete_file_cb(self, action, parameter):
    #     store, paths = self.treeview.get_selection().get_selected_rows()
    #     deleted = [self.store.get_record(self.store.get_iter(p)) for p in paths]
    #     if deleted:
    #         dialog = Gtk.Dialog(parent=self.get_window(), title=_("Move to trash"))
    #         dialog.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
    #         dialog.add_button(_("_OK"), Gtk.ResponseType.OK)
    #         dialog.get_content_area().add(Gtk.Label(label='\n\t'.join([_("Move these files to the trash bin?")] + [song.file for song in deleted])))
    #         reply = dialog.run()
    #         dialog.destroy()
    #         if reply != Gtk.ResponseType.OK:
    #             return
    #         for song in deleted:
    #             if song._gfile is not None:
    #                 song._gfile.trash()
    #                 song._status = self.RECORD_MODIFIED


class SongListTotalsMixin:
    def set_songs(self, songs, **kwargs):
        super().set_songs(songs, **kwargs)
        time = sum(int(song.get('Time', '0')) for song in songs)
        self.status = '{} / {}'.format(len(songs), format_time(time))


class SongListAddSpecialMixin: #####  Not ready
    def __init__(self, unit, *args, **kwargs):
        super().__init__(unit, *args, **kwargs)
        self.actions_dict['songlist'].add_action(resource.Action('add-separator', self.action_add_separator_cb))
        self.actions_dict['songlist'].add_action(resource.Action('add-url', self.action_add_url_cb))

    def action_add_separator_cb(self, action, parameter):
        self.add_record(dict(self.unit.unit_server.separator_song))

    def action_add_url_cb(self, action, parameter):
        struct = ssde.Text(label=_("URL or filename to add"), default='http://')
        url = struct.edit(self.get_window())
        if url:
            self.add_record(dict(file=url))


class UnitSongListMixin(songlistbase.UnitSongListBaseMixin):
    def __init__(self, name, manager, *, menus=[]):
        self.REQUIRED_UNITS = ['songlist'] + self.REQUIRED_UNITS
        super().__init__(name, manager, menus=menus)


class UnitPanedSongListMixin(UnitSongListMixin, component.UnitPanedComponentMixin):
    def __init__(self, name, manager, *, menus=[]):
        super().__init__(name, manager, menus=menus + ['left-context'])
