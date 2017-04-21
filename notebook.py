# Copyright (C) 2007, Eduardo Silva (edsiper@gmail.com)
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

"""Notebook class

This class create a gtk.Notebook() widget supporting 
a close button in every tab when the 'can-close-tabs' gproperty
is enabled (True)

STABLE.
"""

import gtk
import gobject

# Initialize logging.
import logging
from sugar import logger
#Get the standard logging directory. 
std_log_dir = logger.get_logs_dir()
_logger = logging.getLogger('PyDebug')

_logger.setLevel(logging.DEBUG)

class Notebook(gtk.Notebook):
    __gtype_name__ = 'SugarNotebook'

    __gproperties__ = {
        'can-close-tabs': (bool, None, None, False,
                           gobject.PARAM_READWRITE |
                           gobject.PARAM_CONSTRUCT_ONLY)
    }
    __gsignals__ = {
        'do-close-page': (gobject.SIGNAL_RUN_FIRST,
                              gobject.TYPE_NONE,
                              ([]))
    }
    
    def __init__(self, **kwargs):
        # Initialise the Widget
        #
        #    Side effects: 
        #        Set the 'can-close-tabs' property using **kwargs
        #        Set True the scrollable notebook property
        
        gobject.GObject.__init__(self, **kwargs)

        self._can_close_tabs = None
        self.interactive_close = False
        self.set_scrollable(True)
        self.show()

    def do_set_property(self, pspec, value):
        """
        Set notebook property

        Parameters
        ----------
        pspec :
            property for which the value will be set

        Returns
        -------
        None

        Raises
        ------
        AssertionError

        """
        if pspec.name == 'can-close-tabs':
            self._can_close_tabs = value
        else:
            raise AssertionError

    def _add_icon_to_button(self, button):
        icon_box = gtk.HBox()
        image = gtk.Image()
        image.set_from_stock(gtk.STOCK_CLOSE, gtk.ICON_SIZE_MENU)
        gtk.Button.set_relief(button, gtk.RELIEF_NONE)

        settings = gtk.Widget.get_settings(button)
        w, h = gtk.icon_size_lookup_for_settings(settings, gtk.ICON_SIZE_MENU)
        gtk.Widget.set_size_request(button, w + 4, h + 4)
        image.show()
        icon_box.pack_start(image, True, False, 0)
        button.add(icon_box)
        icon_box.show()

    def _create_custom_tab(self, text, child):
        event_box = gtk.EventBox()

        tab_box = gtk.HBox(False, 2)
        self.tab_label = gtk.Label(text)

        tab_button = gtk.Button()
        tab_button.connect('clicked', self._close_page, child)

        # Add a picture on a button
        self._add_icon_to_button(tab_button)

        event_box.show()
        tab_button.show()
        self.tab_label.show()

        tab_box.pack_start(self.tab_label, True)
        tab_box.pack_start(tab_button, True)

        tab_box.show_all()
        event_box.add(tab_box)
        
        return event_box

    def add_page(self, text_label, widget):
        """
        Adds a page to the notebook.

        Parameters
        ----------
        text_label :

        widget :

        Returns
        -------
        #Boolean
          #Returns TRUE if the page is successfully added to th notebook.

        """
        # Add a new page to the notebook
        if self._can_close_tabs:
            eventbox = self._create_custom_tab(text_label, widget)
            self.append_page(widget, eventbox)		
        else:
            self.append_page(widget, gtk.Label(text_label))
            
        pages = self.get_n_pages()

        # Set the new page
        self.set_current_page(pages - 1)
        self.show_all()
        
        return True

    def _close_page(self, button, child):
        # Remove a page from the notebook
        page = self.page_num(child)
        self.emit('do-close-page')
