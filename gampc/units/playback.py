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


class __unit__(unit.UnitMixinServer, unit.Unit):
    def __init__(self, name, manager):
        super().__init__(name, manager)

        self.new_resource_provider('app.action').add_resources(
            resource.ActionModel('play-or-pause', self.play_or_pause_cb, dangerous=True),
            resource.ActionModel('volume', self.change_volume_cb, parameter_type=GLib.VariantType.new('i')),
            resource.ActionModel('absolute-jump', self.absolute_jump_cb, dangerous=True, parameter_type=GLib.VariantType.new('i')),
            resource.ActionModel('relative-jump', self.relative_jump_cb, dangerous=True, parameter_type=GLib.VariantType.new('i')),
            *(resource.ActionModel(name, self.mpd_command_cb, dangerous=True) for name in ('play', 'stop', 'next', 'previous')),
            resource.ActionModel('fadeout-then', self.fadeout_then_cb, parameter_type=GLib.VariantType.new('b')),
        )

        self.new_resource_provider('app.menu').add_resources(
            resource.MenuPath('playback/play'),
            resource.MenuPath('playback/move'),
            resource.MenuPath('playback/volume'),
            resource.MenuPath('playback/jump'),
            resource.UserAction('app.play-or-pause', _("_Play/pause"), 'playback/play', ['<Control>Up', 'AudioPlay', 'space'], accels_fragile=True),
            resource.UserAction('app.stop', _("_Stop"), 'playback/play', ['<Control>Down', 'AudioStop'], accels_fragile=True),
            resource.UserAction('app.fadeout-then(true)', _("Stop [fadeout]"), 'playback/play', ['<Control><Shift>Down', '<Shift>AudioStop'], accels_fragile=True),
            resource.UserAction('app.previous', _("_Previous"), 'playback/move', ['<Control>Left', 'AudioPrev'], accels_fragile=True),
            resource.UserAction('app.next', _("_Next"), 'playback/move', ['<Control>Right', 'AudioNext'], accels_fragile=True),
            resource.UserAction('app.fadeout-then(false)', _("Next [fadeout]"), 'playback/move', ['<Control><Shift>Right'], accels_fragile=True),
            resource.UserAction('app.volume(5)', _("Volume up"), 'playback/volume', ['<Control>plus', '<Control>KP_Add']),
            resource.UserAction('app.volume(-5)', _("Volume down"), 'playback/volume', ['<Control>minus', '<Control>KP_Subtract']),
            resource.UserAction('app.absolute-jump(0)', _("Restart playback"), 'playback/jump', ['<Alt>Up'], accels_fragile=True),
            resource.UserAction('app.absolute-jump(-15)', _("End of song (-{} seconds)").format(15), 'playback/jump', ['<Alt>Down'], accels_fragile=True),
            resource.UserAction('app.relative-jump(-5)', _("Skip backwards ({} seconds)").format(5), 'playback/jump', ['<Alt>Left'], accels_fragile=True),
            resource.UserAction('app.relative-jump(5)', _("Skip forwards ({} seconds)").format(5), 'playback/jump', ['<Alt>Right'], accels_fragile=True),
        )

        self.fading = False

    @ampd.task
    async def mpd_command_cb(self, caller, *data):
        if not self.unit_server.ampd_server_properties.state:
            await self.ampd.idle(ampd.IDLE)
        await getattr(self.ampd, caller.get_name())()

    @ampd.task
    async def play_or_pause_cb(self, action_, parameter):
        if not self.unit_server.ampd_server_properties.state:
            await self.ampd.idle(ampd.IDLE)
        await (self.ampd.pause(1) if self.unit_server.ampd_server_properties.state == 'play' else self.ampd.play())

    @ampd.task
    async def fadeout_then_cb(self, action_, parameter):
        if self.fading:
            return
        stop = parameter.unpack()
        self.fading = True
        N = 30
        T = 5

        try:
            if not self.unit_server.ampd_server_properties.state:
                await self.ampd.idle(ampd.IDLE)
            if self.unit_server.ampd_server_properties.state != 'play':
                return
            volume = self.unit_server.ampd_server_properties.volume
            for i in reversed(range(N)):
                # self.unit_server.ampd_server_properties.volume = volume * i / N
                await self.ampd.setvol(volume * i // N)
                reply = await self.ampd.idle(ampd.PLAYER, timeout=T / N)
                if reply & ampd.PLAYER:
                    self.unit_server.ampd_server_properties.volume = volume
                    return
            nextsong = await self.ampd.playlistid(self.unit_server.ampd_server_properties.nextsongid)
            if nextsong[0]['file'] == self.unit_server.SEPARATOR_FILE:
                sep_id = None
            else:
                sep_id = await self.ampd.addid(self.unit_server.SEPARATOR_FILE, '+0')
            await self.ampd.next()
            await self.ampd.idle(ampd.PLAYER)
            await self.ampd.idle(0, timeout=0.1)  # Something needs to stabilise after the 'next' command.
            # self.unit_server.ampd_server_properties.volume = volume
            await self.ampd.setvol(volume)

            if sep_id is not None:
                await self.ampd.next()
            if stop:
                await self.ampd.stop()
            if sep_id is not None:
                await self.ampd.deleteid(sep_id)
        finally:
            self.fading = False

    def change_volume_cb(self, action_, parameter):
        volume = self.unit_server.ampd_server_properties.volume + parameter.unpack()
        if volume < 0:
            volume = 0
        if volume > 100:
            volume = 100
        self.unit_server.ampd_server_properties.volume = volume

    def absolute_jump_cb(self, action_, parameter):
        target = parameter.unpack()
        if self.unit_server.ampd_server_properties.state != 'stop':
            self.unit_server.ampd_server_properties.elapsed = target if target >= 0 else self.unit_server.ampd_server_properties.duration + target

    def relative_jump_cb(self, action_, parameter):
        if self.unit_server.ampd_server_properties.state != 'stop':
            self.unit_server.ampd_server_properties.elapsed += parameter.unpack()
