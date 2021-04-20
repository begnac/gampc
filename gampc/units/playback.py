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

import ampd

from gampc.util import resource
from gampc.util import unit


class __unit__(unit.UnitWithServer):
    def __init__(self, name, manager):
        super().__init__(name, manager)

        self.new_resource_provider('app.action').add_resources(
            resource.ActionModel('play-or-pause', self.play_or_pause_cb, dangerous=True),
            resource.ActionModel('absolute-jump', self.absolute_jump_cb, dangerous=True, parameter_type=GLib.VariantType.new('i')),
            resource.ActionModel('relative-jump', self.relative_jump_cb, dangerous=True, parameter_type=GLib.VariantType.new('i')),
            *(resource.ActionModel(name, self.mpd_command_cb, dangerous=True) for name in ('play', 'stop', 'next', 'previous')),
            *(resource.ActionModel('fade-to-' + name, self.fade_to_action_cb) for name in ('next', 'stop')),
        )

        self.new_resource_provider('app.menu').add_resources(
            resource.MenuPath('playback/play'),
            resource.MenuPath('playback/move'),
            resource.MenuPath('playback/jump'),
        )

        self.new_resource_provider('app.user-action').add_resources(
            resource.UserAction('app.play-or-pause', _("_Play/pause"), 'playback/play', ['<Control>Up', 'AudioPlay', 'space'], accels_fragile=True),
            resource.UserAction('app.stop', _("_Stop"), 'playback/play', ['<Control>Down', 'AudioStop'], accels_fragile=True),
            resource.UserAction('app.fade-to-stop', _("Fade to stop"), 'playback/play', ['<Control><Shift>Down', '<Shift>AudioStop'], accels_fragile=True),
            resource.UserAction('app.previous', _("_Previous"), 'playback/move', ['<Control>Left', 'AudioPrev'], accels_fragile=True),
            resource.UserAction('app.next', _("_Next"), 'playback/move', ['<Control>Right', 'AudioNext'], accels_fragile=True),
            resource.UserAction('app.fade-to-next', _("_Fade to next"), 'playback/move', ['<Control><Shift>Right'], accels_fragile=True),
            resource.UserAction('app.absolute-jump(0)', _("Restart playback"), 'playback/jump', ['<Alt>Up'], accels_fragile=True),
            resource.UserAction('app.absolute-jump(-15)', _("End of song (-{} seconds)").format(15), 'playback/jump', ['<Alt>Down'], accels_fragile=True),
            resource.UserAction('app.relative-jump(-5)', _("Skip backwards ({} seconds)").format(5), 'playback/jump', ['<Alt>Left'], accels_fragile=True),
            resource.UserAction('app.relative-jump(5)', _("Skip forwards ({} seconds)").format(5), 'playback/jump', ['<Alt>Right'], accels_fragile=True),
        )

        self.fading = None

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
    async def fade_to_action_cb(self, action_, parameter):
        self.fading, running = action_.get_name()[8:], self.fading is not None
        if running:
            return
        try:
            N = 30
            T = 5

            if not self.unit_server.ampd_server_properties.state:
                await self.ampd.idle(ampd.IDLE)
            if self.unit_server.ampd_server_properties.state != 'play':
                return
            volume = self.unit_server.ampd_server_properties.volume
            for i in range(N):
                self.unit_server.ampd_server_properties.volume = volume * (N - i - 1) / N
                reply = await self.ampd.idle(ampd.PLAYER, timeout=T / N)
                if reply & ampd.PLAYER:
                    break
            else:
                await getattr(self.ampd, self.fading)()
            self.unit_server.ampd_server_properties.volume = volume
        finally:
            self.fading = None

    def absolute_jump_cb(self, action_, parameter):
        target = parameter.unpack()
        if self.unit_server.ampd_server_properties.state != 'stop':
            self.unit_server.ampd_server_properties.elapsed = target if target >= 0 else self.unit_server.ampd_server_properties.duration + target

    def relative_jump_cb(self, action_, parameter):
        if self.unit_server.ampd_server_properties.state != 'stop':
            self.unit_server.ampd_server_properties.elapsed += parameter.unpack()
