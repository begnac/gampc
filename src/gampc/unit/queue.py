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

import ampd

from ..util import unit

from ..components import queue

from . import mixins


@ampd.task
async def action_queue_add_replace_cb(songlist_, action, parameter):
    filenames = songlist_.get_filenames(parameter.get_boolean())
    replace = '-replace' in action.get_name()
    if replace:
        await songlist_.ampd.clear()
    await songlist_.ampd.command_list(songlist_.ampd.add(filename) for filename in filenames)
    if replace:
        await songlist_.ampd.play()


@ampd.task
async def action_queue_add_high_priority_cb(songlist_, action, parameter):
    filenames = songlist_.get_filenames(parameter.get_boolean())
    queue = {song['file']: song for song in await songlist_.ampd.playlistinfo()}
    Ids = []
    for filename in filenames:
        Ids.append(queue[filename]['Id'] if filename in queue else await songlist_.ampd.addid(filename))
    await songlist_.ampd.prioid(255, *Ids)


class __unit__(mixins.UnitComponentMixin, mixins.UnitCssMixin, unit.Unit):
    title = _("Play Queue")
    key = '1'

    ##############################    TODO : merge playing CSS with stream

    COMPONENT_CLASS = queue.Queue
    CSS = f'''
    columnview.queue > listview > row > cell.{queue.QUEUE_PRIORITY_CSS_PREFIX}- {{
      background: rgba(0,255,0,0.5);
    }}
    '''

    def __init__(self, *args):
        super().__init__(*args)
        self.require('database')
        self.require('songlist')
        self.require('persistent')

        return

        self.add_resources(
            'itemlist.action',
            resource.ActionModel('queue-ext-add-high-priority', action_queue_add_high_priority_cb,
                                 dangerous=True, parameter_type=GLib.VariantType.new('b')),
            *(resource.ActionModel('queue-ext' + verb, action_queue_add_replace_cb,
                                   dangerous=(verb == '-replace'), parameter_type=GLib.VariantType.new('b'))
              for verb in ('-add', '-replace')),
        )

        for name, parameter in (('context', '(true)'), ('left-context', '(false)')):
            self.add_resources(
                f'itemlist.{name}.menu',
                resource.MenuAction('action', 'itemlist.queue-ext-add' + parameter, _("Add to play queue")),
                resource.MenuAction('action', 'itemlist.queue-ext-replace' + parameter, _("Replace play queue")),
                resource.MenuAction('action', 'itemlist.queue-ext-add-high-priority' + parameter, _("Add to play queue with high priority")),
            )