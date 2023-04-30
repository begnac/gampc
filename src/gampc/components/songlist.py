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


from gi.repository import GLib
from gi.repository import Gio
from gi.repository import Gtk

from ..util import ssde
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
        self.actions_dict['songlist'].add_action(resource.Action('delete-file', self.action_delete_file_cb))

    def records_set_fields(self, songs):
        for song in songs:
            gfile = Gio.File.new_for_path(GLib.build_filenamev([self.unit.unit_songlist.config.music_dir._get(), song['file']]))
            if gfile.query_exists():
                song['_gfile'] = gfile
            else:
                song['_status'] = self.RECORD_MODIFIED
        super().records_set_fields(songs)

    def action_delete_file_cb(self, action, parameter):
        store, paths = self.treeview.get_selection().get_selected_rows()
        deleted = [self.store.get_record(self.store.get_iter(p)) for p in paths]
        if deleted:
            dialog = Gtk.Dialog(parent=self.win, title=_("Move to trash"))
            dialog.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
            dialog.add_button(_("_OK"), Gtk.ResponseType.OK)
            dialog.get_content_area().add(Gtk.Label(label='\n\t'.join([_("Move these files to the trash bin?")] + [song.file for song in deleted]), visible=True))
            reply = dialog.run()
            dialog.destroy()
            if reply != Gtk.ResponseType.OK:
                return
            for song in deleted:
                if song._gfile is not None:
                    song._gfile.trash()
                    song._status = self.RECORD_MODIFIED


class SongListWithTotals(SongList):
    def set_records(self, songs, set_fields=True):
        super().set_records(songs, set_fields)
        time = sum(int(song.get('Time', '0')) for song in songs)
        self.status = '{} / {}'.format(len(songs), format_time(time))


class SongListWithEditDel(SongList, songlistbase.SongListBaseWithEditDel):
    pass


class SongListWithAdd(SongList, songlistbase.SongListBaseWithAdd):
    def __init__(self, unit):
        super().__init__(unit)
        self.actions_dict['songlist'].add_action(resource.Action('add-separator', self.action_add_separator_cb))
        self.actions_dict['songlist'].add_action(resource.Action('add-url', self.action_add_url_cb))

    def action_add_separator_cb(self, action, parameter):
        self.add_record(dict(self.unit.unit_server.separator_song))

    def action_add_url_cb(self, action, parameter):
        struct = ssde.Text(label=_("URL or filename to add"), default='http://')
        url = struct.edit(self.win)
        if url:
            self.add_record(dict(file=url))


class SongListWithEditDelNew(SongListWithAdd, songlistbase.SongListBaseWithEditDelNew):
    pass


# class SongListWithEditDelFile(SongListWithEditDel):
#     def action_save_cb(self, action, parameter):
#         self.save_files(song for i, p, song in self.store)

#     def action_save_selected_cb(self, action, parameter):
#         songs, refs = self.treeview.get_selection_rows()

#     def save_files(self, songs):
#         deleted = [song for song in songs if song._status == self.RECORD_DELETED]
#         if deleted:
#             dialog = Gtk.Dialog(parent=self.win, title=_("Move to trash"))
#             dialog.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
#             dialog.add_button(_("_OK"), Gtk.ResponseType.OK)
#             dialog.get_content_area().add(Gtk.Label(label='\n\t'.join([_("Move these files to the trash?")] + [song.file for song in deleted]), visible=True))
#             reply = dialog.run()
#             dialog.destroy()
#             if reply != Gtk.ResponseType.OK:
#                 return
#             for song in deleted:
#                 song._gfile.trash()
#                 song._status = self.RECORD_UNDEFINED

#     def set_modified(self):
#         self.status = _("modified")

#     def set_records(self, songs, set_fields=True):
#         self.status = None
#         super().set_records(songs, set_fields)


class UnitMixinSongList(songlistbase.UnitMixinSongListBase):
    def __init__(self, name, manager, *, menus=[]):
        self.REQUIRED_UNITS = ['songlist'] + self.REQUIRED_UNITS
        super().__init__(name, manager, menus=menus)


class UnitMixinPanedSongList(UnitMixinSongList, component.UnitMixinPanedComponent):
    def __init__(self, name, manager, *, menus=[]):
        super().__init__(name, manager, menus=menus + ['left-context'])
