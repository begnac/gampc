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

from ..util import action
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
    def __init__(self, manager):
        super().__init__(manager)
        self.require('database')
        self.fading = False

    def generate_actions(self):
        yield action.ActionInfo('play-or-pause', self.play_or_pause_cb, _("_Play/pause"), ['<Alt>Up', 'AudioPlay', 'space'], dangerous=True)
        yield action.ActionInfo('play', self.mpd_command_cb, dangerous=True)
        yield action.ActionInfo('stop', self.mpd_command_cb, _("_Stop"), ['<Alt>Down', 'AudioStop'], dangerous=True)
        yield action.ActionInfo('next', self.mpd_command_cb, _("_Next"), ['<Alt>Right', 'AudioNext'], dangerous=True)
        yield action.ActionInfo('previous', self.mpd_command_cb, _("_Previous"), ['<Alt>Left', 'AudioPrev'], dangerous=True)
        fadeout = action.ActionInfo('fadeout-then', self.fadeout_then_cb, arg_format='b')
        yield fadeout
        yield fadeout.derive(_("Stop [fadeout]"), ['<Alt>End', '<Shift>AudioStop'], True)
        yield fadeout.derive(_("Next [fadeout]"), ['<Alt>Page_Down'], False)
        yield action.ActionInfo('volume-popup', self.volume_popup_cb, _("Adjust volume"), ['<Alt>v'])
        volume = action.ActionInfo('volume', self.volume_cb, arg_format='(ib)', dangerous=True)
        yield volume
        yield volume.derive(_("Volume up"), ['<Control>plus', '<Control>KP_Add'], (5, True))
        yield volume.derive(_("Volume down"), ['<Control>minus', '<Control>KP_Subtract'], (-5, True))
        yield volume.derive(_("Mute"), ['<Control>AudioMute'], (0, False))
        jump = action.ActionInfo('jump', self.jump_cb, arg_format='(ib)', dangerous=True)
        yield jump
        yield jump.derive(_("Restart playback"), ['<Shift><Alt>Up'], (0, False))
        yield jump.derive(_("End of song (-{} seconds)").format(15), ['<Shift><Alt>Down'], (-15, False))
        yield jump.derive(_("Skip backwards ({} seconds)").format(5), ['<Shift><Alt>Left'], (-5, True))
        yield jump.derive(_("Skip forwards ({} seconds)").format(5), ['<Shift><Alt>Right'], (5, True))

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
            if nextsong[0]['file'] == self.unit_database.SEPARATOR_FILE:
                sep_id = None
            else:
                sep_id = await self.ampd.addid(self.unit_database.SEPARATOR_FILE, '+0')
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
        button = Gtk.Application.get_default().get_active_window().headerbar.volume_button
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
