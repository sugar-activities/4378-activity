# Copyright (C) 2009, George Hunt <georgejhunt@gmail.com>
# Copyright (C) 2009, One Laptop Per Child
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

#Python modules needed
from __future__ import with_statement
from gettext import gettext as _
import os, os.path, ConfigParser, shutil, sys
from subprocess import Popen, PIPE
import gtk
import gtk.glade
import pickle
import time
import datetime
import gobject

#sugar stuff
from sugar.graphics.toolbutton import ToolButton
import sugar.graphics.toolbutton
import sugar.env
from sugar.graphics.xocolor import XoColor
from sugar.graphics.icon import Icon
from sugar.datastore import datastore
import sugar.activity.bundlebuilder as bundlebuilder
from sugar.bundle.activitybundle import ActivityBundle
from sugar.activity.activity import Activity
from sugar import profile

#application stuff
from terminal_gui import TerminalGui
from editor import  S_WHERE
from editor import GtkSourceview2Page
from editor_gui import EditorGui
from page import SearchOptions, S_WHERE
from project_gui import ProjectGui
from project import ProjectFunctions
from util import Utilities
from help import Help
import pytoolbar

#public api for ipython
#from IPython.core import ipapi #0.11 requires this
#changes to debugger.py line 508, magic.py:1567
import IPython.ipapi

#following taken from Rpyc module
#import Rpyc 
from Rpyc.Utils.Serving import start_threaded_server, threaded_server_close, DEFAULT_PORT
from Rpyc.Servers import forking_server
from Rpyc.Connection import *
from Rpyc.Stream import *
import select

#from pytoolbar import ActivityToolBox
#from IPython.frontend.terminal.embed import InteractiveShellEmbed

#import logging
from  pydebug_logging import _logger, log_environment, log_dict

"""
High level description of main functions and where stuff might be found:
FOUR MAIN FUNCTIONS:
Application tabs (left to ight)
1. Activity -- the text mode IPython debug screen
2. Editor -- GtkSourceview2
3. Project -- Navigation and file management page (using glade.xml specification)
4. Help -- HTML browser with offline help for PyDebug, Pygtk, etc

The Project Page is the startup screen. The left side of the screen depicts all
the sources and destinations for python programs, Activities, templates.  The
right side of the screen represents the program that is being debugged.

The files in the top level directory are somewhat structured by function:
A. debugger     terminal.py         pretty much direct copy of Terminal.activity
                terminal_gui.py     Gui interface for terminal.py
                pytoolbar.py        reworked sugar.graphics.toolbar
                main650.py          sugar.main.py reworked from build 650
                ipython_config.py   config file for IPython package
B. editor       editor.py           slightly modified develop.activity
                editor_gui.py       Action routines for gui buttons, find window
                vibrant.xml         style for sourceview2 TextView in editor.py
                notebook.py         includes delete button on tab from Develop
C.  project     pydebug.py          Top level application,
                project.py          low level routines for creating xo and tar.gz
                project_gui.py      glade interface and required callbacks
                datastoretree.py    Journal treeview
                filetree.py         folder/file treeview placed in glade screen
                util.ply            generally useful to more than one module
                project.glade       xml gui spec generated by glade3 tool
D.  Help        browser.py          from Help.activity
                progresslistener.py ditto   
                webview.py          ditto
"""
MASKED_ENVIRONMENT = [
    'DBUS_SESSION_BUS_ADDRESS',
    'PPID'
]

#global module variable communicates to debugged programs
global pydebug_instance
pydebug_instance = None

start_clock = 0

class PyDebugActivity(Activity, TerminalGui, EditorGui, ProjectGui):
    #ipshell = IPShellEmbed()
    MIME_TYPE = 'application/vnd.olpc-sugar'
    DEPRECATED_MIME_TYPE = 'application/vnd.olpc-x-sugar'
    MIME_ZIP = 'application/zip'
    _zipped_extension = '.xo'
    _unzipped_extension = '.activity'
    dirty = False
    #global start_clock
    
    def __init__(self, handle):
        #handle object contains command line inputs to this activity
        self.handle = handle
        _logger.debug('Activity id:%s.Object id: %s. uri:%s'%(handle.activity_id, 
                    handle.object_id, handle.uri))
        self.passed_in_ds_object = None
        if handle.object_id and handle.object_id != '':
            self.passed_in_ds_object = datastore.get(handle.object_id)
            if self.passed_in_ds_object:
                d = self.passed_in_ds_object.metadata
                #log_dict(d,'initial datastore metadata ==>:')
        else:
            ds_object = self.get_new_dsobject()
            if hasattr(ds_object, 'get_object_id'):
                handle.object_id = ds_object.get_object_id()
            else:
                handle.object_id = ds_object.object_id
            _logger.debug('no initial datastore object id passed in via handle')

        #Save a global poiinter so remote procedure calls can communicate with pydebug
        global pydebug_instance
        pydebug_instance = self
        start_clock = time.clock()

        #init variables
        self.make_paths()
        self.save_icon_clicked = False
        self.source_directory = None
        self.data_file = None
        self.help = None
        self.help_x11 = None
        self.dirty = False
        self.sock = None
        #self.last_filename = None
        self.debug_dict = {}
        self.activity_dict = {}
        self.manifest_treeview = None  #set up to recognize an re-display of playpen
        #self.set_title(_('PyDebug Activity'))
        self.ds = None #datastore pointer
        self._logger = _logger
        self.traceback = 'Context'
        self.abandon_changes = False
        self.delete_after_load = None
        self.find_window = None
        self.icon_outline = 'icon_square'
        self.icon_window = None
        self.last_icon_file = None
        self.activity_data_changed = False
        self.icon_basename = None
        
        #sugar 0.82 has a different way of getting colors and dies during init unless the following
        self.profile = profile.get_profile()
        self.profile.color = XoColor()
        
        #get the persistent data across all debug sessions and start using it
        self.get_config ()
        
        #give the server a chance to get started so terminal can connect to it
        self.non_blocking_server()
        #glib.idle_add(self.non_blocking_server)
        """
        if self.request_new_jobject and self.debug_dict.get('jobject_id','') != '':
            self.request_new_jobject = False
    
        #keep on using the same journal entry
        if self.debug_dict.get('jobject_id','') != '':
            handle.object_id = self.debug_dict.get('jobject_id','')
        """
        
        # init the Classes we are subclassing
        _logger.debug('about to init  superclass activity. Elapsed time: %f'%\
                      (time.clock()-start_clock))
        Activity.__init__(self, handle,  create_jobject = False)
        """
        if self.request_new_jobject:
            #check to see if the object was created
            if self._jobject:
                self.debug_dict['jobject_id'] = str(self._jobject.object_id)
            else:
                _logger.debug('failed to create jobject in Activity.__init__')
        """
        self.connect('realize',self.realize_cb)
        self.accelerator = gtk.AccelGroup()
        self.add_accel_group(self.accelerator)
        
        #set up the PANES for the different functions of the debugger
        _logger.debug('about to set up Menu panes. Elapsed time: %f'%(time.clock()-start_clock))
        self.panes = {}
        PANES = ['TERMINAL','EDITOR','PROJECT','HELP']
        for i in range(len(PANES)):
            self.panes[PANES[i]] = i
            
        #toolbox needs to be available during init of modules
        self.toolbox = pytoolbar.ActivityToolbox(self)
        self.toolbox.connect_after('current_toolbar_changed',self._toolbar_changed_cb)
        self.toolbox.set_current_toolbar(self.panes['TERMINAL'])

        #########################################################################################
        #init the sub functions
        TerminalGui.__init__(self, self, self.toolbox)
        EditorGui.__init__(self, self)
        ProjectGui.__init__(self,self)
        self.help = Help(self)
        self.util = Utilities(self)            
        #########################################################################################
        
        #if first time run on this machine, set up home directory
        if not os.path.isfile(os.path.join(self.debugger_home,'.bashrc')):
            self.setup_home_directory()
        
        # setup the search options
        self.s_opts = SearchOptions(where = S_WHERE.file,
                                    use_regex = False,
                                    ignore_caps = True,
                                    replace_all = False,
                                    
                                    #defaults to avoid creating
                                    #a new SearchOptions object for normal searches
                                    #should never be changed, just make a copy like:
                                    #SearchOptions(self.s_opts, forward=False)
                                    forward = True, 
                                    stay = False
                                    )
        self.safe_to_replace = False
        
        #get the sugar version
        (major,minor,micro,release) = self._activity.util.sugar_version()
        _logger.debug('sugar version major:%s minor:%s micro:%s release:%s'%(major,minor,micro,release))
        if not minor:
            minor = 70
        self.sugar_minor = minor
        
        #########################################################################################
            
        _logger.debug('All app objects created. about to set up Display . Elapsed time: %f'%(time.clock()-start_clock))
        self.canvas_list = []
        self.canvas_list.append(self._get_terminal_canvas())
        self.canvas_list.append(self._get_edit_canvas()) 
        self.canvas_list.append(self._get_project_canvas()) 
        self.canvas_list.append(self._get_help_canvas())
        
        nb = gtk.Notebook()
        nb.show()
        nb.set_show_tabs(False)
        
        for c in self.canvas_list:
            nb.append_page(c)            
        self.pydebug_notebook = nb

        #the following call to the activity code puts our notebook under the stock toolbar
        self.set_canvas(nb)
                
        helpbar = self.help.get_help_toolbar()

        self.toolbox.add_toolbar(_('Edit'), self.get_editbar())
        self.toolbox.add_toolbar(_('Project'), self.get_projectbar())
        self.toolbox.add_toolbar(_('Help'), self.help.get_help_toolbar())
        self.set_toolbox(self.toolbox)
        self.toolbox.show()
        
        #set which PANE is visible initially
        self.set_visible_canvas(self.panes['PROJECT'])
        self.set_toolbar(self.panes['PROJECT'])
        
        _logger.debug('about to setup_project_page. Elapsed time: %f'%(time.clock()-start_clock))
        self.setup_project_page()
        _logger.debug('about Returned from setup_project_page. Elapsed time: %f'%(time.clock()-start_clock))
        
        #get the journal datastore information and resume previous activity
        #self.metadata = self.ds
        if self.passed_in_ds_object and self.passed_in_ds_object.get_file_path():
            ds_file = self.passed_in_ds_object.get_file_path()
        else:
            ds_file = ''
        _logger.debug('about to  call read  routine  Elapsed time: %f'%(time.clock()-start_clock))
        self.read_file(ds_file)
        _logger.debug('about  (end of init) Elapsed time: %f'%(time.clock()-start_clock))
        
    #########################################################################################

    def get_activity_toolbar(self):
        """pass toolbox to subclassed objects"""
        return self.toolbox
    
    def get_editor(self):
        return self
        
    def get_accelerator(self):
        """override terminal_gui's method"""
        return self.accelerator
    
    def realize_cb(self):
        _logger.debug('about total time to realize event: %f'%(time.clock()-start_clock))
        
    def py_stop(self):
        self.__stop_clicked_cb(None)
        
    def __stop_clicked_cb(self,button):
        _logger.debug('caught stop clicked call back')
        #threaded_server_close()
        self.help.close_pydoc()
        self.save_all_breakpoints()
        self.close(skip_save = False)
        
      
    def non_blocking_server(self):
        start_threaded_server()
        #gobject.idle_add(start_threaded_server)
        #forking_server.main()
    
    def new_pane(self,funct,i):
        self.panes[PANES[i]] = i
        self.canvas_list.append(funct())
        i += 1
        return i
    
    def make_paths(self):
        self.pydebug_path = os.environ['SUGAR_BUNDLE_PATH']
        p_path = os.environ['SUGAR_BUNDLE_PATH']
        if os.environ.get("PYTHONPATH",'') == '':
            os.environ['PYTHONPATH'] = self.pydebug_path
        else:
            p_path_list = os.environ['PYTHONPATH'].split(':')
            if not self.pydebug_path in p_path_list:
                os.environ['PYTHONPATH'] = self.pydebug_path + ':' + os.environ.get("PYTHONPATH",'')
        _logger.debug('sugar_bundle_path:%s\nsugar_activity_root:%s'%(os.environ['SUGAR_BUNDLE_PATH'],
                                                                      os.environ['SUGAR_ACTIVITY_ROOT']))
        self.debugger_home = os.path.join(os.environ['SUGAR_ACTIVITY_ROOT'],'data')
        self.child_path = None
        os.environ["HOME"]=self.debugger_home
        path_list = os.environ['PATH'].split(':')
        new_path = os.path.join(self.pydebug_path,'bin:')
        if not new_path in path_list:
            os.environ['PATH'] = new_path + os.environ['PATH']
        self.storage = os.path.join(os.environ['SUGAR_ACTIVITY_ROOT'],'data/pydebug')
        self.sugar_bundle_path = os.environ['SUGAR_BUNDLE_PATH']
        self.activity_playpen = os.path.join(self.storage,'playpen')
        if not os.path.isdir(self.activity_playpen):
            os.makedirs(self.activity_playpen)
        self.hide = os.path.join(self.storage,'.hide')
        if not os.path.isdir(self.hide):
            os.makedirs(self.hide)
        _logger.debug('Set IPYTHONDIR to %s'%self.debugger_home)
        os.environ['IPYTHONDIR'] = self.debugger_home
    
    def setup_home_directory(self):
        """The directory which Sugar activities have permission to write in"""
        src = os.path.join(self.pydebug_path,'bin','.bashrc')
        try:
            shutil.copy(src,self.debugger_home)
        except Exception,e:
            _logger.exception('copy .bashrc exception %r'%e)
            
        src = os.path.join(self.pydebug_path, 'ipythonrc')
        try:
            shutil.copy(src,self.debugger_home)
        except Exception,e:
            _logger.exception('copy ipthonrc exception %r'%e)
            
        """
        try:
            shutil.rmtree(os.path.join(self.debugger_home,'.ipython'))
        except Exception,e:
            pass
            #_logger.debug('rmtree exception %r trying to setup .ipython '%e)
        """
        try:
            """ definitions for ipythin 0.11
            src = os.path.join(self.pydebug_path,'ipython_config_embeded.py')
            dest = os.path.join(self.debugger_home,'ipython_config.py')
            """
            src = os.path.join(self.pydebug_path,'ipy_user_conf.py')
            dest = os.path.join(self.debugger_home,'ipy_user_conf.py')
            _logger.debug('copying %s to %s'%(src,dest,))
            shutil.copy(src,dest)
        except Exception,e:
            _logger.exception('copy exception %r trying to copy ipython_config.py'%e)
            
        #for build 802 (sugar 0.82) we need a config file underneath home -- which pydebug moves
        # we will place the config file at ~/.sugar/default/
        try:
            shutil.rmtree(os.path.join(self.debugger_home,'.sugar'))
        except Exception,e:
            pass
            _logger.debug('rmtree exception %r trying to setup .ipython '%e)
        try:
            shutil.copytree(os.path.join(self.pydebug_path,'bin','.sugar'),self.debugger_home)
        except Exception,e:
            _logger.exception('copytree exception %r trying to copy .sugar directory'%e)
        #make sure we will have write permission when rainbow changes our identity
        self.util.set_permissions(self.debugger_home)
        
    def _get_edit_canvas(self):
        return self.edit_notebook
           
        
        
        
    def set_ipython_traceback(self):
        tb = self.debug_dict['traceback']
        _logger.debug('set traceback:%s'%tb)
        """
        ip = IPython.ipapi.get()
        if ip:
            ip.ipmagic('xmode %s'%tb)
        else:
            _logger.error('did not get ip from IPython.ipapi')
        #ipmagic = ip.user_ns['ipmagic']
        #ip.magic_xmode(tb)
        """
        self.feed_virtual_terminal(0,"%%xmode %s\n"%tb)
        gobject.idle_add(self.set_terminal_focus)

    def find_import(self,fn):
        _logger.debug('find_import in file %s'%fn)
        try_fn = os.path.join(self.child_path,fn)
        if not os.path.isfile(try_fn):
            try_fn += '.py'
            if not os.path.isfile(try_fn):
                _logger.debug('in find_import, failed to find file %s'%try_fn)
                return
            line_no = 0
            for line in open(try_fn,'r'):
                if line.startswith('import'):
                    return line_no, try_fn
                line_no += 1
            return -1, None    
                    
    def _get_child_canvas(self):
        fr = gtk.Frame()
        label = gtk.Label("This page will be replaced with the \noutput from your program")
        label.show()       
        fr.add(label)
        fr.show()
        return fr

             
    def _get_help_canvas(self):
        fr = gtk.Frame()
        label = gtk.Label(_("Loading Help Page"))
        label.show()       
        fr.add(label)
        fr.show()
        return fr

    def get_icon_pixbuf(self, stock):
        return self.treeview.render_icon(stock_id=getattr(gtk, stock),
                                size=gtk.ICON_SIZE_MENU,
                                detail=None)

 

    #lots of state to change whenever one of the major tabs is clicked    
    def set_visible_canvas(self,index): #track the toolbox tab clicks
        self.pydebug_notebook.set_current_page(index)
        if index == self.panes['TERMINAL']:
            gobject.idle_add(self.set_terminal_focus)
            self.save_all()
            if self.icon_window:
                self.icon_window.hide()
        elif index == self.panes['HELP']:
            self.help_selected()
        elif index == self.panes['PROJECT'] and self.get_manifest_class():
            self.manifest_class.set_file_sys_root(self.child_path)
        if self.icon_window:
            self.icon_window.destroy()
        if not index == self.panes['EDITOR'] and self.find_window:
            self.find_window.hide()
        self.current_pd_page = index
        gobject.idle_add(self.grab_notebook_focus)
        
    def grab_notebook_focus(self):
        self.pydebug_notebook.grab_focus()
        return False
                
    def _toolbar_changed_cb(self,widget,tab_no):
        _logger.debug('tool tab changed notification %d'%tab_no)
        self.set_visible_canvas(tab_no)
        
    def set_toolbar(self,page_no):
        self.toolbox.set_current_toolbar(page_no)
        
    def key_press_cb(self,widget,event):
        state = event.get_state()
        if state and gtk.gdk.SHIFT_MASK and gtk.gdk.CONTROL_MASK and gtk.gdk.MOD1_MASK == 0:
            self.file_changed = True
            #put a star in front of the filename
        return False
    

    ######  SUGAR defined read and write routines -- do not let them overwrite what's being debugged
    
    def read_file(self, file_path):
        """
        If the ds_object passed to PyDebug is the last one saved, then just assume that the playpen is valid.
        If the ds_object is not the most recent one,  try to load the playpen with the contents referenced by the git_id
        (reading the wiki, I discover we cannot count on metadata -- so cancel the git_id scheme)
        """
        #keep our own copy of the metadata
        if self.metadata:
            for key in self.metadata.keys():  #merge in journal information
                self.activity_dict[key] = self.metadata[key]
        log_dict(self.activity_dict,"read_file merged")
        if not self.debug_dict: self.get_config()
        if self.activity_dict.get('uid','XxXxXx') == self.debug_dict.get('jobject_id','YyYyY'):
            _logger.debug('pick up where we left off')
            #OLPC bug reports suggest not all keys are preserved, so restore what we really need
            self.activity_dict['child_path'] = self.debug_dict.get('child_path','')
            if os.path.isdir(self.activity_dict.get('child_path')):
                self.child_path = self.activity_dict['child_path']
                #self.setup_new_activity()
        #update the journal display - required when the journal is used to delete an item
        if self.journal_class: 
            self.journal_class.new_directory()            
                       
    def write_file(self, file_path):
        """
        The paradigm designed into the XO, ie an automatic load from the Journal at activity startup
        does not make sense during a debugging session.  An errant stack overflow can easily crash
        the system and require a reboot.  For the session manager to overwrite the changes that are stored
        on disk, but not yet saved in the journal is  undesireable. So we'll let the user save to
        the journal, and perhaps optionally to the sd card (because it is removable, should the system die)
        """
         
        try:
            self.update_metadata()    
            self.save_editor_status()
            self.put_config()
        except Exception,e:
            _logger.exception('Write file exception %s'%e)
            raise e
        
        try:
            fd = open(file_path,'w+')
            if fd:
                fd.close()
            else:
                _logger.debug('failed to open output file')
        except Exception, e:
            _logger.exception('Write file exception %s'%e)
        return
        
    def update_metadata(self):
        obj = self._jobject
        #ipshell()
        if obj:
            md = obj.get_metadata()
            obj._file_path = None
            if md:
                log_dict(md,'journal metadata')                
                _logger.debug('write file  Jobject passed to write:%s'%(obj.object_id,))
                chunk = self.activity_dict.get('name','')            
                for key in self.activity_dict.keys():
                    if key == 'title' or key == 'activity': continue
                    md[key] = self.activity_dict[key]
                md['title'] = 'PyDebug_' + chunk
                md['title_set_by_user'] = '1'
                md['bundle_id'] = 'org.laptop.PyDebug'
                try:
                    pass
                    #datastore.write(obj)
                except Exception, e:
                    _logger.debug('datastore write exception %s'%e)
            else:
                _logger.error('no metadata in write_file')
        else:
            _logger.error('no jobject in write_file')
            
    def init_activity_dict(self):
        self.activity_dict['version'] = '1'
        #try to disable the annoying save panel asking for new title
        self.activity_dict['title_set_by_user'] = '1'
        self.activity_dict['name'] = 'untitled'
        self.activity_dict['bundle_id'] = ''
        self.activity_dict['command'] = ''
        self.activity_dict['class'] = ''
        self.activity_dict['module'] = ''           
        self.activity_dict['icon'] = ''
        self.activity_dict['activity_id'] = ''
        self.activity_dict['package'] = ''
        self.activity_dict['jobject _id'] = ''
        
    ################  Help routines
    def help_selected(self):
        """
        if help is not created in a gtk.mainwindow then create it
        else just switch to that viewport
        """
        if not self.help_x11:
            screen = gtk.gdk.screen_get_default()
            self.pdb_window = screen.get_root_window()
            _logger.debug('xid for pydebug:%s'%self.pdb_window.xid)
            #self.window_instance = self.window.window
            self.help_x11 = self.help.realize_help()
            #self.x11_window = self.get_x11()os.geteuid()
        else:
            self.help.activate_help()
            #self.help.reshow()
            #self.help.toolbox.set_current_page(self.panes['HELP']
    """
    def get_x11(self):
        home_model = shell.get_model()
        activity = home_model.get_active_activity()
        if activity and activity.get_window():
            
            return activity.get_window().activate(1)
        else:
            return None
    
    def check_child_md5(self):    
        if self.child_path and self.debug_dict.get('tree_md5',''):
            if self.debug_dict.get('tree_md5','') == self.util.md5sum_tree(self.child_path):
                #self.setup_new_activity()
                #the tree is valid so take up where we left off
                pass
            else:
                self.util.confirmation_alert(_('Continue even though stored checksum does not match current checksum'),
                           _('CAUTION: The program in the playpen may have been changed.'),
                           self.startup_continue)
        
    def startup_continue(self,alert,response):
        self.setup_new_activity()
    """    
    def save_editor_status(self):
        if self.edit_notebook.get_n_pages() == 0: return
        current_page = self.edit_notebook.get_current_page()
        edit_files = []
        for i in range(self.edit_notebook.get_n_pages()):
            page = self.edit_notebook.get_nth_page(i)
            if isinstance(page,GtkSourceview2Page):
                i = page.fullPath.find('playpen')
                if i > -1:
                    fname = page.fullPath[i+8:]
                else:
                    fname = page.fullPath
                _logger.debug('updating debug_dict with %s' % fname)
                edit_files.append([fname, page.get_iter().get_line()])
        self.debug_dict[os.path.basename(self.child_path)] = edit_files
        self.debug_dict[os.path.basename(self.child_path)+'-page'] = current_page
    
    def remember_line_no(self,fullPath,line):
        activity_name = self.glean_file_id_from_fullpath(fullPath)
        if activity_name:         
            self.debug_dict[activity_name] = line
        _logger.debug('remembering id:%s at line:%s'%(activity_name,line,))
        
    def glean_file_id_from_fullpath(self,fullPath):
        """use folder name of activity as namespace for filename"""
        folder_list = fullPath.split('/')
        activity_name = ''
        for folder in folder_list:
            if folder.find('.activity') >-1:
                activity_name = folder
        i = folder_list.index(activity_name)
        ret = '/'.join(folder_list[i:])
        _logger.debug('file_id:%s'%ret)
        return ret
    
    def get_remembered_line_number(self,fullPath):
        activity_name = self.glean_file_id_from_fullpath(fullPath)
        if activity_name:
            return self.debug_dict.get(activity_name)
            
    def get_config(self):
        try:
            fd = open(os.path.join(self.debugger_home,'pickl'),'rb')
            local = pickle.load(fd)
            self.debug_dict = local.copy()
            _logger.debug('unpickled successfully')
            """
            object_id = self.debug_dict.get('jobject_id','')
            if object_id != '':
                self._jobject = datastore.get(object_id)
            else:
                self._jobject = None
            """
        except:
            try:
                fd = open(os.path.join(self.debugger_home,'pickl'),'wb')
                self.debug_dict['child_path'] = ''
                local = self.debug_dict.copy()
                pickle.dump(local,fd,pickle.HIGHEST_PROTOCOL)
            except IOError:
                _logger.debug('get_config -- Error writing pickle file %s'
                              %os.path.join(self.debugger_home,'pickl'))
        finally:
            fd.close()
        object_id = self.debug_dict.get('jobject_id','')
        if False: #object_id == '':
            jobject = self.get_new_dsobject()
            self._jobject = jobject
            self.debug_dict['jobject_id'] = str(self._jobject.object_id)
            _logger.debug('in get_config created jobject id:%s'%self.debug_dict['jobject_id'])
        else:
            pass
            #self._jobject = datastore.get(object_id)
        self.child_path = self.debug_dict.get('child_path','')
        if self.child_path == '' or not os.path.isdir(self.child_path):
            self.child_path = None
            
    def get_new_dsobject(self):
        jobject = datastore.create()
        jobject.metadata['title'] = 'PyDebug'
        jobject.metadata['activity'] = 'org.laptop.PyDebug'
        jobject.metadata['keep'] = '1'
        jobject.metadata['preview'] = ''
        datastore.write(jobject)
        return jobject

    def put_config(self):
        if self.child_path:
            #self.debug_dict['tree_md5'] = self.util.md5sum_tree(self.child_path)
            self.debug_dict['child_path'] = self.child_path 
        try:
            fd = open(os.path.join(self.debugger_home,'pickl'),'wb')
            local = self.debug_dict.copy()
            pickle.dump(local,fd,pickle.HIGHEST_PROTOCOL)
        except IOError:
            _logger.debug('put_config routine Error writing pickle file %s'
                          %os.path.join(self.debugger_home,'pickl'))
            return
        finally:
            fd.close()
        #log_dict(self.debug.dict,'put config debug_dict contents:)
            