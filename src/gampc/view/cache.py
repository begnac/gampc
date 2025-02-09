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

from ..util import action
from ..util import aioqueue
from ..util import item
from ..util import misc
from ..ui import dialog

from .actions import ViewWithCopy
from .actions import ViewWithCopyPaste


class ItemFilenameTransfer(item.ItemKeyTransfer):
    pass


class ViewFilenameMixin:
    transfer_type = ItemFilenameTransfer
    extra_transfer_types = (item.ItemStringTransfer,)

    def generate_editing_actions(self):
        yield action.ActionInfo('delete-file', self.action_delete_file_cb, _("Move files to trash"), ['<Control>Delete'])
        yield from super().generate_editing_actions()

    @misc.create_task
    async def action_delete_file_cb(self, action, parameter):
        deleted = self.get_filenames(True)
        if deleted:
            message = '\n\t'.join([_("Move these files to the trash bin?")] + deleted)
            if not await dialog.MessageDialogAsync(transient_for=self.get_root(), title=_("Move to trash"), message=message).run():
                return
            for filename in deleted:
                gfile = Gio.File.new_for_path(GLib.build_filenamev([GLib.get_user_special_dir(GLib.USER_DIRECTORY_MUSIC), filename]))
                print(gfile.trash())
                # continue
                # if song._gfile is not None:
                #     song._gfile.trash()
                #     song._status = self.RECORD_MODIFIED


class ViewWithCopyPasteSong(ViewFilenameMixin, ViewWithCopyPaste):
    def __init__(self, *args, separator_file, **kwargs):
        super().__init__(*args, **kwargs)
        self.separator_file = separator_file

    def generate_editing_actions(self):
        yield from super().generate_editing_actions()
        yield action.ActionInfo('add-separator', self.action_add_separator_cb, _("Add separator"))
        yield from self.generate_url_actions()

    def action_add_separator_cb(self, action, parameter):
        selection = self.get_selection()
        if selection:
            pos = selection[0]
        else:
            return
        self.add_items(pos, [self.separator_file])


class ViewCacheMixin(ViewFilenameMixin):
    def __init__(self, *args, cache, **kwargs):
        super().__init__(*args, **kwargs)
        self.aioqueue = aioqueue.AIOQueue()
        self.cache = cache
        self.item_view.add_css_class('song-by-key')

    def set_keys(self, keys):
        if keys:
            self.splice_keys(0, None, keys)
        else:
            self.item_model.remove_all()

    def splice_keys(self, pos, remove, keys):
        self.aioqueue.queue_task(self._splice_keys, pos, remove, list(keys))

    async def _splice_keys(self, task, pos, remove, keys):
        await self.cache.ensure_keys(keys)
        if task is not None:
            await task
        self.item_model.splice_values(pos, remove, (self.cache[key] for key in keys))


class ViewCacheWithCopy(ViewCacheMixin, ViewWithCopy):
    pass


class ViewCacheWithCopyPaste(ViewCacheMixin, ViewWithCopyPaste):
    pass


class ViewCacheWithCopyPasteSong(ViewCacheMixin, ViewWithCopyPasteSong):
    pass
