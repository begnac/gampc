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


from gi.repository import Gtk

import os

from gampc.util import unit
import gampc


class __unit__(unit.Unit):
    def __init__(self, name, manager):
        super().__init__(name, manager)
        self.uidefs = {}

    def build_ui(self, uiname):
        if uiname in self.uidefs:
            uidef = self.uidefs[uiname]
        else:
            uidef = open(os.path.join(os.path.dirname(gampc.__file__), 'ui', uiname + '.ui')).read()
            self.uidefs[uiname] = uidef
        builder = Gtk.Builder(translation_domain='gampc')
        builder.add_from_string(uidef)
        return builder
