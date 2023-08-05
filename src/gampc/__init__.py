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


import gi
import gettext


gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')


from gi.repository import Gtk


__application__ = 'gampc-gtk4'


gettext.install(__application__)


__program_name__ = "Graphical Asyncronous Music Player Client"
__program_description__ = \
    _("A Music Player Daemon client written in Python/Gtk4, using"
      " asynchronous communication")
__author__ = "Itaï BEN YAACOV"
__copyright__ = "© " + __author__
__license_type__ = Gtk.License.GPL_3_0
__version__ = '0.3.2'
