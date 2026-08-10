"""Graphical Asynchronous Music Player Client."""

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


from gi.repository import GObject

import ampd

from ..util import misc
from ..util import unit
from ..util.logger import logger

from ..ui import dialog

from . import mixins


class __unit__(mixins.UnitServerMixin, unit.Unit):
    __gsignals__ = {
        'cleared': (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, manager):
        super().__init__(manager)
        self.separator = dict(file=misc.SEPARATOR_FILE)

    @ampd.task
    async def client_connected_cb(self, client):
        while True:
            separator = await self.find_song(misc.SEPARATOR_FILE)
            if '_missing' in self.separator:
                await self.separator_missing()
            else:
                self.separator.update(separator)
            await self.ampd.idle(ampd.DATABASE)
            logger.info(_("Database changed"))

    async def find_song(self, key):
        try:
            songs = await self.ampd.find('file', key)
        except Exception as e:
            print(key, type(e))
            songs = []
        if len(songs) == 0:
            song = {'file': key, '_missing': True}
        elif len(songs) == 1:
            song = songs[0]
            misc.song_set_fields(song)
        else:
            raise ValueError
        return song

    async def separator_missing(self):
        await dialog.MessageDialog(title=_("Separator file missing"), message=_("Some features require a file named '{separator}' at the music root directory.  Such a file, consisting of a three second silence, is provided.").format(separator=misc.SEPARATOR_FILE)).run()
