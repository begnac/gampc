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

import ampd

from ..util import resource
from ..util import unit
from ..components import songlist
from ..components import playqueue


@ampd.task
async def action_playqueue_add_replace_cb(songlist_, action, parameter):
    filenames = songlist_.get_filenames(parameter.get_boolean())
    replace = '-replace' in action.get_name()
    if replace:
        await songlist_.ampd.clear()
    await songlist_.ampd.command_list(songlist_.ampd.add(filename) for filename in filenames)
    if replace:
        await songlist_.ampd.play()


@ampd.task
async def action_playqueue_add_high_priority_cb(songlist_, action, parameter):
    filenames = songlist_.get_filenames(parameter.get_boolean())
    queue = {song['file']: song for song in await songlist_.ampd.playlistinfo()}
    Ids = []
    for filename in filenames:
        Ids.append(queue[filename]['Id'] if filename in queue else await songlist_.ampd.addid(filename))
    await songlist_.ampd.prioid(255, *Ids)


class __unit__(songlist.UnitMixinSongList, unit.Unit):
    title = _("Play Queue")
    key = '1'

    COMPONENT_CLASS = playqueue.PlayQueue

    def __init__(self, name, manager):
        super().__init__(name, manager)

        self.add_resources(
            'app.menu',
            resource.MenuAction('edit/component', 'playqueue.shuffle', _("Shuffle")),
            resource.MenuAction('edit/component', 'playqueue.go-to-current', _("Go to current song"), ['<Control>z'])
        )

        self.add_resources(
            'songlistbase.action',
            resource.ActionModel('playqueue-ext-add-high-priority', action_playqueue_add_high_priority_cb,
                                 dangerous=True, parameter_type=GLib.VariantType.new('b')),
            *(resource.ActionModel('playqueue-ext' + verb, action_playqueue_add_replace_cb,
                                   dangerous=(verb == '-replace'), parameter_type=GLib.VariantType.new('b'))
              for verb in ('-add', '-replace')),
        )

        for name, parameter in (('context', '(true)'), ('left-context', '(false)')):
            self.add_resources(
                f'songlistbase.{name}.menu',
                resource.MenuAction('action', 'songlistbase.playqueue-ext-add' + parameter, _("Add to play queue")),
                resource.MenuAction('action', 'songlistbase.playqueue-ext-replace' + parameter, _("Replace play queue")),
                resource.MenuAction('action', 'songlistbase.playqueue-ext-add-high-priority' + parameter, _("Add to play queue with high priority")),
            )

        self.add_resources(
            self.name + '.context.menu',
            resource.MenuPath('other/playqueue-priority', _("Priority for random mode"), is_submenu=True),
            resource.MenuAction('other/playqueue-priority', 'playqueue.high-priority', _("High")),
            resource.MenuAction('other/playqueue-priority', 'playqueue.normal-priority', _("Normal")),
            resource.MenuAction('other/playqueue-priority', 'playqueue.choose-priority', _("Choose")),
            resource.MenuAction('other', 'playqueue.shuffle', _("Shuffle")),
        )
