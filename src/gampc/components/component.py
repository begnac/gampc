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


from gi.repository import GObject
from gi.repository import Gtk

from ..util import misc
from ..util import cleanup


# class Component(cleanup.CleanupSignalMixin, GObject.Object):
#     status = GObject.Property()
#     full_title = GObject.Property(type=str)

#     def __init__(self, unit, *, name=None, **kwargs):
#         super().__init__(full_title=unit.title, **kwargs)
#         self.unit = unit
#         self.name = name or unit.name
#         self.config = self.unit.config
#         self.ampd = self.unit.ampd.sub_executor()

#         self.status_binding = self.bind_property('status', self, 'full-title', GObject.BindingFlags(0), lambda x, y: "{} [{}]".format(unit.title, self.status) if self.status else unit.title)

#         self.connect_clean(unit.unit_server.ampd_client, 'client-connected', self.client_connected_cb)
#         if self.ampd.get_is_connected():
#             self.client_connected_cb(unit.unit_server.ampd_client)

#     def cleanup(self):
#         self.status_binding.unbind()
#         self.ampd.close()
#         del self.widget
#         super().cleanup()

#     @staticmethod
#     def client_connected_cb(client):
#         pass


class ComponentWidget(cleanup.CleanupSignalMixin, Gtk.Box):
    subtitle = GObject.Property(type=str)

    def __init__(self, widget, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect('notify::subtitle', self.notify_subtitle_cb)
        self.connect('map', self.map_cb)
        self.append(widget)

    @staticmethod
    def notify_subtitle_cb(self, pspec):
        window = self.get_root()
        if window is not None:
            window.set_subtitle(self.subtitle)

    @staticmethod
    def map_cb(self):
        self.get_root().set_subtitle(self.subtitle)

    def grab_focus(self):
        self.get_first_child().grab_focus()
