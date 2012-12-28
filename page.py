# -*- coding: utf-8 -*-
#Copyright (c) 2012 Walter Bender

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import gtk
import gobject
import os
import codecs
from random import uniform

from gettext import gettext as _

from utils.play_audio import play_audio_from_file

import logging
_logger = logging.getLogger('iknowmyabcs-activity')

try:
    from sugar.graphics import style
    GRID_CELL_SIZE = style.GRID_CELL_SIZE
except ImportError:
    GRID_CELL_SIZE = 0

from genpieces import generate_card
from utils.sprites import Sprites, Sprite


XDIM = 3
YDIM = 3
GUTTER = 4


class Page():
    ''' Pages from Infuse Reading method '''

    def __init__(self, canvas, lessons_path, images_path, sounds_path,
                 parent=None):
        ''' The general stuff we need to track '''
        self._activity = parent
        self._lessons_path = lessons_path
        self._images_path = images_path
        self._sounds_path = sounds_path

        self._card_data = []
        self._color_data = []
        self._image_data = []
        self._media_data = []  # (image sound, letter sound)
        self._word_data = []

        # Starting from command line
        if self._activity is None:
            self._sugar = False
            self._canvas = canvas
        else:
            self._sugar = True
            self._canvas = canvas
            self._activity.show_all()

        self._canvas.set_flags(gtk.CAN_FOCUS)
        self._canvas.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self._canvas.add_events(gtk.gdk.BUTTON_RELEASE_MASK)
        self._canvas.connect("expose-event", self._expose_cb)
        self._canvas.connect("button-press-event", self._button_press_cb)
        self._canvas.connect("button-release-event", self._button_release_cb)
        self._canvas.connect("key_press_event", self._keypress_cb)
        self._width = gtk.gdk.screen_width()
        self._height = gtk.gdk.screen_height()
        self._card_width = int((self._width / XDIM)) - GUTTER * 2
        self._card_height = int((self._height - GRID_CELL_SIZE) / YDIM) \
            - GUTTER * 2
        self._grid_x_offset = int(
            (self._width - XDIM * (self._card_width + GUTTER * 2)) / 2)
        self._grid_y_offset = 0
        # self._scale = self._width / 240.
        self._scale = self._card_width / 80
        self._sprites = Sprites(self._canvas)
        self.current_card = 0
        self._cards = []
        self._pictures = []
        self._press = None
        self._release = None
        self.timeout = None
        self.target = 0
        self.answers = [0, 0, 0, 0, 0, 0]

        self.load_level(os.path.join(self._lessons_path, 'alphabet' + '.csv'))

        # Create the cards we'll need
        self._alpha_cards()
        self._image_cards()

        self.new_page()

    def new_page(self):
        ''' Load a page of cards '''
        if self.timeout is not None:
            gobject.source_remove(self.timeout)
        self._hide_cards()
        self.new_target()
        x = self._grid_x_offset + self._card_width + GUTTER * 3
        y = self._grid_y_offset + GUTTER
        if self._activity.mode == 'letter':
            self._cards[self.target].move((x, y))
            self._cards[self.target].set_layer(100)
            x = self._grid_x_offset + GUTTER
            y = self._grid_y_offset + self._card_height + GUTTER * 3
            for i in range(len(self.answers)):
                self._pictures[self.answers[i]].move((x, y))
                self._pictures[self.answers[i]].set_layer(100)
                x += self._card_width + GUTTER * 2
                if x > self._width - (self._card_width / 2):
                    x = self._grid_x_offset + GUTTER
                    y += self._card_height + GUTTER * 2
        else:
            self._pictures[self.target].move((x, y))
            self._pictures[self.target].set_layer(100)
            x = self._grid_x_offset + GUTTER
            y = self._grid_y_offset + self._card_height + GUTTER * 3
            for i in range(len(self.answers)):
                self._cards[self.answers[i]].move((x, y))
                self._cards[self.answers[i]].set_layer(100)
                x += self._card_width + GUTTER * 2
                if x > self._width - (self._card_width / 2):
                    x = self._grid_x_offset + GUTTER
                    y += self._card_height + GUTTER * 2

    def _hide_cards(self):
        if len(self._cards) > 0:
            for card in self._cards:
                card.hide()
        if len(self._pictures) > 0:
            for card in self._pictures:
                card.hide()

    def _image_cards(self):
        for card in self._card_data:
            self.current_card = self._card_data.index(card)
            imagefilename = self._image_data[self.current_card]
            imagepath = os.path.join(self._images_path, imagefilename)
            pixbuf = image_file_to_pixbuf(imagepath, self._card_width,
                                          self._card_height)
            self._pictures.append(Sprite(self._sprites, 0, 0, pixbuf))

    def _alpha_cards(self):
        for card in self._card_data:
            self.current_card = self._card_data.index(card)
            # Two-tone cards add some complexity.
            if type(self._color_data[self.current_card][0]) == type([]):
                stroke = self._test_for_stroke()
                top = svg_str_to_pixbuf(generate_card(
                        string=card[0].lower(),
                        colors=[self._color_data[self.current_card][0][0],
                                '#FFFFFF'],
                        scale=self._scale,
                        center=True))
                bot = svg_str_to_pixbuf(generate_card(
                        string=card[0].lower(),
                        colors=[self._color_data[self.current_card][0][1],
                                '#FFFFFF'],
                        scale=self._scale,
                        center=True))
                # Where to draw the line
                h1 = 9 / 16.
                h2 = 1.0 - h1
                bot.composite(top, 0, int(h1 * top.get_height()),
                              top.get_width(), int(h2 * top.get_height()),
                              0, 0, 1, 1, gtk.gdk.INTERP_NEAREST, 255)
                self._cards.append(Sprite(self._sprites, 0, 0, top))
            else:
                stroke = self._test_for_stroke()
                self._cards.append(Sprite(self._sprites, 0, 0,
                                          svg_str_to_pixbuf(generate_card(
                                string=card[0].lower(),
                                colors=[self._color_data[self.current_card][0],
                                        '#FFFFFF'],
                                stroke=stroke,
                                scale=self._scale, center=True))))

    def _test_for_stroke(self):
        ''' Light colors get a surrounding stroke '''
        if self._color_data[self.current_card][0][0:4] == '#FFF':
            return True
        else:
            return False

    def new_target(self):
        ''' Generate a new target and answer list '''
        self._activity.status.set_text(
            _('Click on the card that corresponds to the sound.'))
        self.target = int(uniform(0, len(self._cards)))

        for i in range(6):
            self.answers[i] = self.target
        for i in range(6):
            while self._bad_answer(i):
                self.answers[i] = int(uniform(0, len(self._cards)))
        i = int(uniform(0, 6))
        self.answers[i] = self.target

        if self.timeout is not None:
            gobject.source_remove(self.timeout)
        self.timeout = gobject.timeout_add(1000, self._play_target_sound)

    def _bad_answer(self, i):
        ''' Make sure answer is unique '''
        if self.answers[i] == self.target:
            return True
        for j in range(6):
            if i == j:
                continue
            if self.answers[i] == self.answers[j]:
                return True
        return False

    def _play_target_sound(self):
        if self._activity.mode == 'letter':
            play_audio_from_file(self, os.path.join(
                    self._sounds_path,
                    self._media_data[self.target][1]))
        else:
            play_audio_from_file(self, os.path.join(
                    self._sounds_path,
                    self._media_data[self.target][0]))
        self.timeout = None

    def _button_press_cb(self, win, event):
        ''' Either a card or list entry was pressed. '''
        win.grab_focus()
        x, y = map(int, event.get_coords())

        spr = self._sprites.find_sprite((x, y))
        self._press = spr
        self._release = None
        return True

    def _button_release_cb(self, win, event):
        ''' Play a sound or video or jump to a card as indexed in the list. '''
        win.grab_focus()

        x, y = map(int, event.get_coords())
        spr = self._sprites.find_sprite((x, y))
        self.current_card = -1
        if spr in self._cards:
            self.current_card = self._cards.index(spr)
        elif spr in self._pictures:
            self.current_card = self._pictures.index(spr)
        if self.current_card == -1:
            return

        if self._activity.mode == 'letter':
            if spr in self._cards:
                play_audio_from_file(self, os.path.join(
                        self._sounds_path,
                        self._media_data[self.current_card][1]))
                return
            play_audio_from_file(self, os.path.join(
                    self._sounds_path,
                    self._media_data[self.current_card][0]))
        else:
            if spr in self._pictures:
                play_audio_from_file(self, os.path.join(
                        self._sounds_path,
                        self._media_data[self.current_card][0]))
                return
            play_audio_from_file(self, os.path.join(
                    self._sounds_path,
                    self._media_data[self.current_card][1]))

        if self.current_card == self.target:
            self._activity.status.set_text(_('Very good!'))
            if self.timeout is not None:
                gobject.source_remove(self.timeout)
            self.timeout = gobject.timeout_add(1000, self.new_page)
        else:
            self._activity.status.set_text(_('Please try again.'))
            self._play_target_sound()

    def _keypress_cb(self, area, event):
        ''' No keyboard shortcuts at the moment. Perhaps jump to the page
        associated with the key pressed? '''
        return True

    def _expose_cb(self, win, event):
        ''' Callback to handle window expose events '''
        self.do_expose_event(event)
        return True

    # Handle the expose-event by drawing
    def do_expose_event(self, event):

        # Create the cairo context
        cr = self._canvas.window.cairo_create()

        # Restrict Cairo to the exposed area; avoid extra work
        cr.rectangle(event.area.x, event.area.y,
                event.area.width, event.area.height)
        cr.clip()

        # Refresh sprite list
        self._sprites.redraw_sprites(cr=cr)

    def _destroy_cb(self, win, event):
        ''' Make a clean exit. '''
        gtk.main_quit()

    def invalt(self, x, y, w, h):
        ''' Mark a region for refresh '''
        self._canvas.window.invalidate_rect(
            gtk.gdk.Rectangle(int(x), int(y), int(w), int(h)), False)

    def load_level(self, path):
        ''' Load a level (CSV) from path: letter, word, color, image,
        image sound, letter sound '''
        self._card_data = []
        self._color_data = []
        self._image_data = []
        self._media_data = []  # (image sound, letter sound)
        f = codecs.open(path, encoding='utf-8')
        for line in f:
            if len(line) > 0 and line[0] not in '#\n':
                words = line.split(', ')
                self._card_data.append([words[0], 
                                        words[1].replace('-', ', ')])
                if words[2].count('#') > 1:
                    self._color_data.append(
                        [words[2].split('/')])
                else:
                    self._color_data.append(
                        [words[2]])
                self._image_data.append(words[3])
                self._media_data.append((words[4], words[5]))
        f.close()

        self._clear_all()
        self._cards = []
        self._colored_letters_lower = []
        self._colored_letters_upper = []

    def _clear_all(self):
        ''' Hide everything so we can begin a new page. '''
        self._hide_cards()

def svg_str_to_pixbuf(svg_string):
    ''' Load pixbuf from SVG string. '''
    pl = gtk.gdk.PixbufLoader('svg')
    pl.write(svg_string)
    pl.close()
    pixbuf = pl.get_pixbuf()
    return pixbuf


def image_file_to_pixbuf(file_path, w, h):
    ''' Load pixbuf from file '''
    return gtk.gdk.pixbuf_new_from_file_at_size(file_path, int(w), int(h))
        
