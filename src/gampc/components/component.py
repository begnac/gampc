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

from ..util import cleanup
from ..util.logger import logger


class Component(cleanup.CleanupSignalMixin, GObject.Object):
    status = GObject.Property()
    full_title = GObject.Property(type=str)

    def __init__(self, unit, *, name=None, **kwargs):
        super().__init__(full_title=unit.title, **kwargs)
        self.unit = unit
        self.name = name or unit.name
        self.manager = unit.manager
        self.config = self.unit.config
        self.ampd = self.unit.ampd.sub_executor()

        self.status_binding = self.bind_property('status', self, 'full-title', GObject.BindingFlags(0), lambda x, y: "{} [{}]".format(unit.title, self.status) if self.status else unit.title)

        self.connect_clean(unit.unit_server.ampd_client, 'client-connected', self.client_connected_cb)
        if self.ampd.get_is_connected():
            self.client_connected_cb(unit.unit_server.ampd_client)

    def cleanup(self):
        if self.get_window() is not None:
            raise RuntimeError
        self.status_binding.unbind()
        self.ampd.close()
        del self.widget
        super().cleanup()

    def get_window(self):
        root = self.widget.get_root()
        return root if isinstance(root, Gtk.Window) else None

    @staticmethod
    def client_connected_cb(client):
        pass
