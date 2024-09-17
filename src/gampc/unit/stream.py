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


from gi.repository import GLib

from ..util import action
from ..util import db
from ..util import field
from ..util import item
from ..util import misc
from ..util import unit

from ..ui import dialog

from ..view.actions import ViewWithCopyPaste
from ..view.cache import ItemFilenameTransfer
from ..view.listitem import EditableListItemFactory

from ..control import editstack

from . import mixins


class ItemStreamTransfer(item.ItemValueTransfer):
    pass


class StreamWidget(editstack.WidgetEditStackMixin, ViewWithCopyPaste):
    transfer_type = ItemStreamTransfer
    extra_transfer_types = (ItemFilenameTransfer, item.ItemStringTransfer)

    def __init__(self, separator_file, edit_stack, *args, **kwargs):
        super().__init__(*args, **kwargs, factory_factory=EditableListItemFactory)
        self.item_view.add_css_class('song-by-key')
        for column in self.item_view.get_columns():
            self.connect_clean(column.get_factory(), 'item-edited', self.item_edited_cb)
        self.context_menu.append_section(None, self.edit_stack_menu)
        self.item_view.add_css_class('stream')
        item.setup_find_duplicate_items(self.item_model, ['file'], [separator_file])

        self.set_edit_stack(edit_stack)

    def cleanup(self):
        self.set_edit_stack(None)
        super().cleanup()

    def generate_editing_actions(self):
        yield from super().generate_editing_actions()
        yield from self.generate_url_actions()

    def item_edited_cb(self, factory, pos, name, value):
        GLib.idle_add(self.item_edited, pos, name, value)

    def item_edited(self, pos, name, value):
        old = self.item_selection_model[pos].value
        new = dict(old)
        new[name] = value
        self.edit_stack.hold_transaction()
        self.edit_stack.append_delta(editstack.DeltaSplicer([new], pos, True))
        self.edit_stack.append_delta(editstack.DeltaSplicer([old], pos, False))
        self.edit_stack.release_transaction()

    def action_save_cb(self, action, parameter):
        self.activate_action('stream.save')

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
        self.config.edit_dialog_size._get(default=[500, 500])

        self.require('database')
        self.require('persistent')

        self.fields = field.FieldFamily(self.config.fields)
        self.fields.register_field(field.Field('Name', _("Name")))
        self.fields.register_field(field.Field('file', _("URL"), editable=True))
        self.fields.register_field(field.Field('Comment', _("Comment")))

        self.db = StreamDatabase(self.name, self.fields)
        streams = list(self.db.get_streams())
        for stream in streams:
            stream['Title'] = stream['Name']
            self.unit_database.cache[stream['file']] = stream
            for key in stream:
                if stream[key] is None:
                    stream[key] = ''
        self.edit_stack = editstack.EditStack(streams)

    def factory(self):
        component = super().factory()
        component.connect_clean(self.edit_stack, 'notify::modified', self.notify_modified_cb, component)
        return component

    def notify_modified_cb(self, edit_stack, pspec, component):
        parts = [self.TITLE]
        if edit_stack.modified:
            parts.append(_("[modified]"))
        component.subtitle = ' '.join(parts)

    def new_widget(self):
        stream = StreamWidget(self.unit_database.SEPARATOR_FILE, self.edit_stack, self.fields)
        stream.connect_clean(stream.item_view, 'activate', self.view_activate_cb)
        stream.add_context_menu_actions(self.generate_stream_actions(stream), 'stream', self.TITLE)
        return stream

    def generate_stream_actions(self, widget):
        yield action.ActionInfo('save', self.action_save_cb, activate_args=(widget,))

    @misc.create_task
    async def action_save_cb(self, action, parameter, widget):
        if widget.edit_stack.transactions and await dialog.MessageDialogAsync(transient_for=widget.get_root(), message=_("Save stream database?")).run():
            self.db.save_streams(map(lambda item: item.value, widget.item_model))
            widget.edit_stack.reset()
            widget.edit_stack_changed()

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
