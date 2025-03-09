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


# import os
import re
# import urllib

from gi.repository import GObject

import ampd

from ..util import cache
from ..util import misc
from ..util import unit
from ..util.logger import logger

from ..ui import dialog

from . import mixins


def set_song_fields(song):
    song['Duration'] = misc.format_time(float(song['duration'])) if 'Time' in song else ''

    # title = song.get('Title') or song.get('Name', '')
    # filename = song.get('file', '')
    # url = urllib.parse.urlparse(filename)
    # if url.scheme:
    #     url_basename = os.path.basename(url.path)
    #     title = '{0} [{1}]'.format(title, url_basename) if title else url_basename
    # song['Title'] = title
    song['Title'] = song.get('Title') or song.get('Name') or ''

    match = re.search('\\.(\\w+)$', song['file'])
    if match:
        song['Extension'] = match[1]


class SongCache(cache.AsyncCache):
    def __init__(self, ampd):
        super().__init__()
        self.ampd = ampd

    async def retrieve(self, key):
        try:
            songs = await self.ampd.find('file', key)
        except Exception as e:
            print(key, type(e))
            songs = []
        if len(songs) == 0:
            song = {'file': key, '_missing': True}
        elif len(songs) == 1:
            song = songs[0]
            set_song_fields(song)
        else:
            raise ValueError
        return song


class __unit__(mixins.UnitServerMixin, unit.Unit):
    __gsignals__ = {
        'cleared': (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    SEPARATOR_FILE = 'separator.mp3'

    def __init__(self, manager):
        super().__init__(manager)
        self.cache = SongCache(self.ampd)

    def cleanup(self):
        super().cleanup()
        del self.cache

    @ampd.task
    async def client_connected_cb(self, client):
        while True:
            self.cache.clear()
            self.emit('cleared')
            if '_missing' in await self.cache.get_async(self.SEPARATOR_FILE):
                await self.separator_missing()
            await self.ampd.idle(ampd.DATABASE)
            logger.info(_("Database changed"))

    def update(self, songs):
        for song in songs:
            set_song_fields(song)
            self.cache[song['file']] = song

    async def separator_missing(self):
        await dialog.MessageDialogAsync(cancel_button=False,
                                        message=_("Some features require a file named '{separator}' at the music root directory.  Such a file, consisting of a three second silence, is provided.").format(separator=self.SEPARATOR_FILE)).run()
