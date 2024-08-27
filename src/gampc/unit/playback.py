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

import asyncio
import ampd

from ..util import actions
from ..util import unit

from . import mixins


def hold_app(f):
    def g(*args, **kwargs):
        app = Gtk.Application.get_default()
        retval = f(*args, **kwargs)
        if isinstance(retval, asyncio.Future):
            app.hold()
            retval.add_done_callback(lambda future: app.release())
        return retval
    return g


class __unit__(mixins.UnitServerMixin, unit.Unit):
    def __init__(self, *args):
        super().__init__(*args)
        self.fading = False

    def generate_actions(self):
        yield actions.ActionInfo('play-or-pause', self.play_or_pause_cb, _("_Play/pause"), ['<Control>Up', 'AudioPlay', 'space'], dangerous=True)
        yield actions.ActionInfo('play', self.mpd_command_cb, dangerous=True)
        yield actions.ActionInfo('stop', self.mpd_command_cb, _("_Stop"), ['<Control>Down', 'AudioStop'], dangerous=True)
        yield actions.ActionInfo('next', self.mpd_command_cb, _("_Next"), ['<Control>Right', 'AudioNext'], dangerous=True)
        yield actions.ActionInfo('previous', self.mpd_command_cb, _("_Previous"), ['<Control>Left', 'AudioPrev'], dangerous=True)
        fadeout = actions.ActionInfo('fadeout-then', self.fadeout_then_cb, parameter_format='b')
        yield fadeout
        yield fadeout.derive(_("Stop [fadeout]"), ['<Control><Shift>Down', '<Shift>AudioStop'], True)
        yield fadeout.derive(_("Next [fadeout]"), ['<Control><Shift>Right'], False)
        yield actions.ActionInfo('volume-popup', self.volume_popup_cb, _("Adjust volume"), ['<Alt>v'])
        volume = actions.ActionInfo('volume', self.volume_cb, parameter_format='(ib)')
        yield volume
        yield volume.derive(_("Volume up"), ['<Control>plus', '<Control>KP_Add'], (5, True))
        yield volume.derive(_("Volume down"), ['<Control>minus', '<Control>KP_Subtract'], (-5, True))
        yield volume.derive(_("Mute"), ['<Control>AudioMute'], (0, False))
        jump = actions.ActionInfo('jump', self.jump_cb, parameter_format='(ib)')
        yield jump
        yield jump.derive(_("Restart playback"), ['<Alt>Up'], (0, False))
        yield jump.derive(_("End of song (-{} seconds)").format(15), ['<Alt>Down'], (-15, False))
        yield jump.derive(_("Skip backwards ({} seconds)").format(5), ['<Alt>Left'], (-5, True))
        yield jump.derive(_("Skip forwards ({} seconds)").format(5), ['<Alt>Right'], (5, True))

    @hold_app
    @ampd.task
    async def mpd_command_cb(self, caller, *data):
        if not self.unit_server.ampd_server_properties.state:
            await self.ampd.idle(ampd.IDLE)
        await getattr(self.ampd, caller.get_name())()

    @hold_app
    @ampd.task
    async def play_or_pause_cb(self, action_, parameter):
        if not self.unit_server.ampd_server_properties.state:
            await self.ampd.idle(ampd.IDLE)
            await self.ampd.idle(ampd.IDLE)
        await (self.ampd.pause(1) if self.unit_server.ampd_server_properties.state == 'play' else self.ampd.play())

    @hold_app
    @ampd.task
    async def fadeout_then_cb(self, action_, parameter):
        if self.fading:
            return
        stop = parameter.unpack()
        self.fading = True
        N = 30
        T = 7

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

    def volume_popup_cb(self, action, parameter):
        button = self.app.get_active_window().headerbar.volume_button
        if button.is_sensitive() and not button.get_popup().get_mapped():
            button.emit('popup')
        else:
            button.emit('popdown')

    def volume_cb(self, action_, parameter):
        volume, relative = parameter.unpack()
        if relative:
            volume += self.unit_server.ampd_server_properties.volume
        if volume < 0:
            volume = 0
        if volume > 100:
            volume = 100
        self.unit_server.ampd_server_properties.volume = volume

    def jump_cb(self, action_, parameter):
        target, relative = parameter.unpack()
        if self.unit_server.ampd_server_properties.state != 'stop':
            if relative:
                target += self.unit_server.ampd_server_properties.elapsed
            elif target < 0:
                target = self.unit_server.ampd_server_properties.duration + target
            self.unit_server.ampd_server_properties.elapsed = target