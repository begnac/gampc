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


from gi.repository import Gtk

from .. import util
from .. import ui

from . import itemlist
from . import component


class SongList(itemlist.ItemList):
    use_resources = ['itemlist', 'songlist']
    DND_TARGET = 'GAMPC_SONG'

    def __init__(self, unit, *args, **kwargs):
        self.fields = unit.unit_songlist.fields
        super().__init__(unit, *args, widget_factory=lambda: Gtk.Label(halign=Gtk.Align.START), item_store=util.item.ItemListStore(self.item_factory), **kwargs)
        self.songlist_actions = self.add_actions_provider('songlist')
        # self.songlist_actions.add_action(resource.Action('delete-file', self.action_delete_file_cb))

    def shutdown(self):
        del self.songlist_actions
        super().shutdown()

    def item_factory(self):
        return util.item.ItemFromCache(self.unit.database)

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
        self.status = '{} / {}'.format(len(songs), util.misc.format_time(time))


class SongListAddSpecialMixin:  #####  Not ready
    def __init__(self, unit, *args, **kwargs):
        super().__init__(unit, *args, **kwargs)
        self.actions_dict['songlist'].add_action(util.resource.Action('add-separator', self.action_add_separator_cb))
        self.actions_dict['songlist'].add_action(util.resource.Action('add-url', self.action_add_url_cb))

    def action_add_separator_cb(self, action, parameter):
        self.add_record(dict(self.unit.unit_server.separator_song))

    def action_add_url_cb(self, action, parameter):
        struct = ui.ssde.Text(label=_("URL or filename to add"), default='http://')
        url = struct.edit(self.get_window())
        if url:
            self.add_record(dict(file=url))


@util.unit.require_units('songlist')
class UnitSongListMixin(itemlist.UnitItemListMixin):
    pass


class UnitPanedSongListMixin(UnitSongListMixin, component.UnitPanedComponentMixin):
    def __init__(self, name, manager, *, menus=[]):
        super().__init__(name, manager, menus=menus + ['left-context'])
