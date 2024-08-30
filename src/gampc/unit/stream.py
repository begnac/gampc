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

from ..util import action
from ..util import db
from ..util import editstack
from ..util import field
from ..util import item
from ..util import misc
from ..util import unit

from ..ui import dialog

from ..view.base import EditableItemFactory
from ..view.editstack import ViewWithEditStack
from ..view.cache import ItemFilenameTransfer
from ..view.cache import ViewWithCopyPasteSong

from ..components import itemlist

from . import mixins


STREAM_URL_CSS_PREFIX = 'stream-url'


def encode_url(url):
    return url.encode().hex()


class StreamItemFactory(EditableItemFactory):
    @staticmethod
    def value_binder(widget, item, name):
        misc.add_unique_css_class(widget.get_parent(), STREAM_URL_CSS_PREFIX, encode_url(item.get_key()))
        EditableItemFactory.value_binder(widget, item, name)


class ItemStreamTransfer(item.ItemValueTransfer):
    pass


class StreamView(ViewWithEditStack):
    transfer_type = ItemStreamTransfer
    extra_transfer_types = (ItemFilenameTransfer, item.ItemStringTransfer)

    edit_stack_splicer = ViewWithEditStack.splice_values

    @staticmethod
    def edit_stack_getter(item):
        return item.value

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for column in self.item_view.get_columns():
            column.get_factory().connect('item-edited', self.item_edited_cb)

    def cleanup(self):
        for column in self.item_view.get_columns():
            column.get_factory().disconnect_by_func(self.item_edited_cb)
        super().cleanup()

    def generate_editing_actions(self):
        yield from super().generate_editing_actions()
        yield from self.generate_url_actions()

    def item_edited_cb(self, factory, pos, name, value):
        old = self.item_selection_model[pos].value
        new = dict(old)
        new[name] = value
        self.edit_stack.hold_transaction()
        self.edit_stack.append_delta(editstack.Delta([old], pos, False))
        self.edit_stack.append_delta(editstack.Delta([new], pos + 1, True))
        self.edit_stack.release_transaction()


class Stream(itemlist.ItemList):
    factory_factory = StreamItemFactory

    def __init__(self, unit):
        super().__init__(unit)

        self.view.add_to_context_menu(self.generate_save_actions(), 'stream', _("Save"))

        self.widget.item_view.add_css_class('stream')

        self.signal_handler_connect(self.unit.unit_server, 'notify::current-song', self.notify_current_song_cb)

        self.css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(self.widget.get_display(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.load_streams()

    def create_view(self, view_class=StreamView):
        return super().create_view(StreamView)

    def generate_save_actions(self):
        yield action.ActionInfo('save', self.action_save_cb, _("Save"), ['<Control>s'])

    @misc.create_task
    async def action_save_cb(self, action, parameter):
        if self.view.edit_stack.transactions and await dialog.MessageDialogAsync(transient_for=self.widget.get_root(), message=_("Save stream database?")).run():
            self.unit.db.save_streams(self.view.edit_stack.items)
            self.view.edit_stack.reset()
            self.view.edit_stack_changed()

    def get_fields(self):
        return self.unit.fields

    def load_streams(self):
        streams = list(self.unit.db.get_streams())
        for stream in streams:
            for key in stream:
                if stream[key] is None:
                    stream[key] = ''
        self.view.set_edit_stack(editstack.EditStack(streams))

    def notify_current_song_cb(self, server_properties, pspec):
        url = server_properties.current_song.get('file')
        if url is not None and (url.startswith('http://') or url.startswith('https://')):
            PLAYING_CSS = f'''
            columnview.stream > listview > row > cell.{STREAM_URL_CSS_PREFIX}-{encode_url(url)} {{
              background: rgba(128,128,128,0.1);
              font-style: italic;
              font-weight: bold;
            }}
            '''
        else:
            PLAYING_CSS = ''
        self.css_provider.load_from_string(PLAYING_CSS)


class StreamDatabase(db.Database):
    def __init__(self, name, fields):
        self.fields = fields
        super().__init__(name)

    def setup_database(self):
        self.setup_table('streams', 'streamid INTEGER PRIMARY KEY', self.fields.basic_names)

    def get_streams(self):
        query = self.connection.cursor().execute('SELECT streamid,{} FROM streams'.format(','.join(self.fields.basic_names)))
        return map(lambda s: {name: s[i] for i, name in enumerate(['streamid'] + self.fields.basic_names)}, query)

    def save_streams(self, streams):
        with self.connection:
            self.connection.cursor().execute('DELETE FROM streams')
            for stream_ in streams:
                self.connection.cursor().execute('INSERT OR IGNORE INTO streams({}) VALUES({})'.format(','.join(self.fields.basic_names),
                                                                                                       ':' + ',:'.join(self.fields.basic_names)), stream_)


class __unit__(mixins.UnitComponentMixin, mixins.UnitCssMixin, unit.Unit):
    title = _("Internet Streams")
    key = '4'

    COMPONENT_CLASS = Stream
    CSS = '''
    columnview.stream > listview > row > cell.playing {
      background: rgba(128,128,128,0.1);
      font-style: italic;
      font-weight: bold;
    }
    columnview > listview > row > cell > editablelabel:focus {
      outline-color: yellow;
      outline-offset: 0px;
      outline-style: solid;
      outline-width: 4px;
    }
    '''

    def __init__(self, *args):
        super().__init__(*args)

        self.require('database')
        self.require('persistent')

        self.fields = field.FieldFamily(self.config.fields)
        self.fields.register_field(field.Field('Name', _("Name")))
        self.fields.register_field(field.Field('file', _("URL"), editable=True))
        self.fields.register_field(field.Field('Comment', _("Comment")))

        self.db = StreamDatabase(self.name, self.fields)
        for song in self.db.get_streams():
            song['Title'] = song['Name']
            self.unit_database.cache[song['file']] = song

        self.config.edit_dialog_size._get(default=[500, 500])

    # def current_song_hook(self, song):
    #     if 'file' not in song or 'Title' not in song:
    #         return
    #     url = song['file']
    #     if not url.startswith('http://') and not url.startswith('https://'):
    #         return
    #     orig_title = title = song['Title']
    #     artist = song.get('Artist')
    #     performer = song.get('Performer')
    #     name = song.get('Name')
    #     if artist is None and ' - ' in title:
    #         artist, title = title.split(' - ', 1)
    #     if performer is None and ' & ' in artist:
    #         artist, performer = artist.split(' & ', 1)
    #     if name is not None:
    #         title += f' [{name}]'
    #     song.update(Title=title, Artist=artist, Performer=performer)

    #     logger.info(orig_title)
