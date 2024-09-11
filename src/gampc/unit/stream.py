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


from ..util import action
from ..util import db
from ..util import editstack
from ..util import field
from ..util import item
from ..util import misc
from ..util import unit

from ..ui import dialog

from ..view.editstack import ViewWithEditStack
from ..view.cache import ItemFilenameTransfer
from ..view.listitem import EditableListItemFactory

from . import mixins


class ItemStreamTransfer(item.ItemValueTransfer):
    pass


class StreamWidget(ViewWithEditStack):
    transfer_type = ItemStreamTransfer
    extra_transfer_types = (ItemFilenameTransfer, item.ItemStringTransfer)

    @staticmethod
    def edit_stack_getter(item):
        return item.value

    def __init__(self, separator_file, db, *args, **kwargs):
        self.db = db
        super().__init__(*args, **kwargs, factory_factory=EditableListItemFactory)
        self.item_view.add_css_class('song-by-key')
        for column in self.item_view.get_columns():
            self.connect_clean(column.get_factory(), 'item-edited', self.item_edited_cb)
        self.add_context_menu_actions(self.generate_save_actions(), 'stream', _("Save"))
        self.item_view.add_css_class('stream')
        item.setup_find_duplicate_items(self.item_model, ['file'], [separator_file])

        self.load_streams()

    def generate_editing_actions(self):
        yield from super().generate_editing_actions()
        yield from self.generate_url_actions()

    def item_edited_cb(self, factory, pos, name, value):
        old = self.item_selection_model[pos].value
        new = dict(old)
        new[name] = value
        self.edit_stack.hold_transaction()
        self.edit_stack.append_delta(editstack.DeltaSplicer([old], pos, False, self.edit_stack_splicer))
        self.edit_stack.append_delta(editstack.DeltaSplicer([new], pos + 1, True, self.edit_stack_splicer))
        self.edit_stack.release_transaction()

    def generate_save_actions(self):
        yield action.ActionInfo('save', self.action_save_cb, _("Save"), ['<Control>s'])

    @misc.create_task
    async def action_save_cb(self, action, parameter):
        if self.edit_stack.transactions and await dialog.MessageDialogAsync(transient_for=self.get_root(), message=_("Save stream database?")).run():
            self.db.save_streams(self.edit_stack.items)
            self.edit_stack.reset()
            self.edit_stack_changed()

    def load_streams(self):
        streams = list(self.db.get_streams())
        for stream in streams:
            for key in stream:
                if stream[key] is None:
                    stream[key] = ''
        self.set_edit_stack(editstack.EditStack(streams))

    def edit_stack_splicer(self, pos, remove, values):
        self.item_model.splice_values(pos, remove, values)


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


class __unit__(mixins.UnitComponentQueueActionMixin, mixins.UnitConfigMixin, unit.Unit):
    TITLE = _("Internet Streams")
    KEY = '4'

    def __init__(self, manager):
        super().__init__(manager)

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

    def new_widget(self):
        stream = StreamWidget(self.unit_database.SEPARATOR_FILE, self.db, self.fields)
        stream.connect_clean(stream.item_view, 'activate', self.view_activate_cb)
        return stream

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
