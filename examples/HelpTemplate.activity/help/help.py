# Copyright (C) 2006, Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import os, sys
from gettext import gettext as _
from subprocess import Popen, PIPE
import shutil

import gtk
import gobject
import wnck
#from time import time
from sugar import util

from sugar.activity import activity
from sugar.graphics.window import Window
from sugar.graphics.toolbox import Toolbox
from sugar.activity.activityhandle import ActivityHandle
from sugar import wm, env
#from IPython.Debugger import Tracer
from pdb import *
from sugar.graphics.toolbutton import ToolButton

import hulahop
#hulahop.startup(os.path.join(activity.get_activity_root(), 'data/gecko'))
hulahop.startup(os.path.join(os.environ['SUGAR_ACTIVITY_ROOT'], 'data/gecko'))
import xpcom
from xpcom.nsError import *
#from xpcom import components
#from xpcom.components import interfaces
from browser import Browser
from xpcom.components import interfaces

"""#from hulahop.webview import WebView
from browser import Browser
import xpcom
from xpcom.components import interfaces
"""
gobject.threads_init()

HELP_PANE = 1

# Initialize logging.
import logging
_logger = logging.getLogger('HelpTemplate')

class Help(Window):
    def __init__(self, parent):
        self.parent_obj = parent
        
        if version < 0.838: 
            from hulahop.webview import WebView as Browser
        else:
            from browser import Browser
        
        self.help_id = None
        self.handle = ActivityHandle()
        self.handle.activity_id = util.unique_id()
        Window.__init__(self)
        self.connect('realize',self.realize_cb)

        self._web_view = Browser()

        #determine which language we are going to be using
        help_root = self.get_help_root()
        self.HOME = os.path.join(help_root, 'HelpApi.htm')
    
        self.toolbox = Toolbox()
        self.toolbox.connect('current_toolbar_changed',self.goto_cb)
        self.set_toolbox(self.toolbox)
        self.toolbox.show()
        
        activitybar = gtk.Toolbar()
        self.toolbox.add_toolbar(_('Activity'), activitybar)
        activitybar.show_all()
        
        self.help_toolbar = Toolbar(self._web_view, self)
        self.help_toolbar.show()
        self.toolbox.add_toolbar(_('Help'), self.help_toolbar)
        self.toolbox._notebook.set_current_page(HELP_PANE)

        self.set_canvas(self._web_view)
        self._web_view.show()

        self.toolbox.set_current_toolbar(HELP_PANE)

        self._web_view.load_uri(self.HOME)

    def get_help_toolbar(self):
        return self.help_toolbar

    def realize_help(self):

        #trial and error suggest the following parent activation is necesssary to return reliably to parent window
        if version > 0.839:
            self.pywin = self.get_wnck_window_from_activity_id(str(self.parent_obj.handle.activity_id))
            if self.pywin:
                self.pywin.activate(gtk.get_current_event_time())
                _logger.debug('pywin.activate called')
        self.show_all()
        self.toolbox._notebook.set_current_page(HELP_PANE)
        return self
    
    def realize_cb(self, window):
        self.help_id = util.unique_id()
        wm.set_activity_id(window.window, self.help_id)
        self.help_window = window
            
    def activate_help(self):
        _logger.debug('activate_help called')
        self.help_window.show()
        if version < 0.838: return
        window = self.get_wnck_window_from_activity_id(self.help_id)
        self.toolbox._notebook.set_current_page(HELP_PANE)
        if window:
            window.activate(gtk.get_current_event_time())
        else:
            _logger.debug('failed to get window')
            
    def close (self):
        self.goto_cb(None, 0)
        self.parent_obj.py_stop()
            
    def goto_cb(self, page, tab):
        _logger.debug('current_toolbar_changed event called goto_cb. tab: %s'%tab)
        if tab == HELP_PANE: return
        if not self.help_id: return
        self.parent_obj.set_toolbar(tab)
        self.help_window.hide()
        if version < 0.838: return
        self.pywin = self.get_wnck_window_from_activity_id(str(self.parent_obj.handle.activity_id))
        if self.pywin:
            self.pywin.activate(gtk.get_current_event_time())

    def get_wnck_window_from_activity_id(self, activity_id):
        """Use shell model to look up the wmck window associated with activity_id
           --the home_model code changed between .82 and .84 sugar
           --so do the lookup differently depending on sugar version
        """
        _logger.debug('get_wnck_window_from_activity_id. id:%s'%activity_id)
        _logger.debug('sugar version %s'%version)
        if version and version >= 0.839:
            home_model = shell.get_model()
            activity = home_model.get_activity_by_id(activity_id)
        else:
            instance = view.Shell.get_instance()
            home_model = instance.get_model().get_home()
            activity = home_model._get_activity_by_id(activity_id)
        if activity:
            return activity.get_window()
        else:
            _logger.debug('wnck_window was none')
            return None
        
    def get_help_root(self):
        lang = os.environ.get('LANGUAGE')
        if not lang:
            lang = os.environ.get('LANG')
        if not lang:
            lang = 'en_US'
        if len(lang) > 1:
            two_char = lang[:2]
        else:
            two_char = ''
        root = os.path.join(os.environ['SUGAR_BUNDLE_PATH'],'help',two_char)
        if os.path.isdir(root):
            return root
        root = os.path.join(os.environ['SUGAR_ACTIVITY_ROOT'],'help',two_char)
        if os.path.isdir(root):
            return root
        #default to a non localized root
        root = os.path.join(os.environ['SUGAR_BUNDLE_PATH'],'help')
        return root
    
class Toolbar(gtk.Toolbar):
    def __init__(self, web_view, _help):
        gobject.GObject.__init__(self)

        self._web_view = web_view
        self._help = _help

        self._back = ToolButton('go-previous-paired')
        self._back.set_tooltip(_('Back'))
        self._back.props.sensitive = False
        self._back.connect('clicked', self._go_back_cb)
        self.insert(self._back, -1)
        self._back.show()

        self._forward = ToolButton('go-next-paired')
        self._forward.set_tooltip(_('Forward'))
        self._forward.props.sensitive = False
        self._forward.connect('clicked', self._go_forward_cb)
        self.insert(self._forward, -1)
        self._forward.show()

        home = ToolButton('zoom-home')
        home.set_tooltip(_('Home'))
        home.connect('clicked', self._go_home_cb)
        self.insert(home, -1)
        home.show()

        separator = gtk.SeparatorToolItem()
        separator.set_draw(False)
        separator.set_expand(True)
        self.insert(separator, -1)
        separator.show()

        stop_button = ToolButton('activity-stop')
        stop_button.set_tooltip(_('Stop'))
        #stop_button.props.accelerator = '<Ctrl>Q'
        stop_button.connect('clicked', self.__stop_clicked_cb)
        self.insert(stop_button, -1)
        stop_button.show()
        
        if version < 0.838:
            self._listener = xpcom.server.WrapObject(EarlyListener(self),
                                                     interfaces.nsIWebProgressListener)
            weak_ref = xpcom.client.WeakReference(self._listener)
    
            mask = interfaces.nsIWebProgress.NOTIFY_STATE_NETWORK | \
                   interfaces.nsIWebProgress.NOTIFY_LOCATION
            self._web_view.web_progress.addProgressListener(self._listener, mask)
        else:
        
            progress_listener = self._web_view.progress
            progress_listener.connect('location-changed',
                                      self._location_changed_cb)
            progress_listener.connect('loading-stop', self._loading_stop_cb)

        

    def __stop_clicked_cb(self, button):
        self._help.close()
        
    def _location_changed_cb(self, progress_listener, uri):
        self.update_navigation_buttons()

    def _loading_stop_cb(self, progress_listener):
        self.update_navigation_buttons()
        
    def update_navigation_buttons(self):
        can_go_back = self._web_view.web_navigation.canGoBack
        self._back.props.sensitive = can_go_back

        can_go_forward = self._web_view.web_navigation.canGoForward
        self._forward.props.sensitive = can_go_forward

    def _go_back_cb(self, button):
        self._web_view.web_navigation.goBack()
    
    def _go_forward_cb(self, button):
        self._web_view.web_navigation.goForward()

    def _go_home_cb(self, button):
        self._web_view.load_uri(HOME)

class EarlyListener(object):
    #from xpcom.components import interfaces

    _com_interfaces_ = interfaces.nsIWebProgressListener

    def __init__(self, toolbar):
        self._toolbar = toolbar
    
    def onLocationChange(self, webProgress, request, location):
        self._toolbar.update_navigation_buttons()
        
    def onProgressChange(self, webProgress, request, curSelfProgress,
                         maxSelfProgress, curTotalProgress, maxTotalProgress):
        pass
    
    def onSecurityChange(self, webProgress, request, state):
        pass
        
    def onStateChange(self, webProgress, request, stateFlags, status):
        if stateFlags & interfaces.nsIWebProgressListener.STATE_IS_NETWORK:
            self._toolbar.update_navigation_buttons()

    def onStatusChange(self, webProgress, request, status, message):
        pass
  

def command_line(cmd):
    _logger.debug('command_line cmd:%s'%cmd)
    p1 = Popen(cmd,stdout=PIPE, shell=True)
    output = p1.communicate()
    if p1.returncode != 0:
        return None
    return output[0]
    
def sugar_version():
    cmd = '/bin/rpm -q sugar'
    reply = command_line(cmd)
    if reply and reply.find('sugar') > -1:
        version = reply.split('-')[1]
        version_chunks = version.split('.')
        major_minor = version_chunks[0] + '.' + version_chunks[1]
        return float(major_minor) 
    return None

version = 0.0
version = sugar_version() 
if version and version >= 0.839:
    from jarabe.model import shell
else:
    if not '/usr/share/sugar/shell/' in sys.path:
        sys.path.append('/usr/share/sugar/shell/')
    import view.Shell

