#!/usr/bin/env python
# encoding: utf-8
"""
The main IPython application object

Authors:

* Brian Granger
* Fernando Perez

Notes
-----
"""

#-----------------------------------------------------------------------------
#  Copyright (C) 2008-2009  The IPython Development Team
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

import logging
import os
import sys
import warnings

from IPython.core.application import Application, IPythonArgParseConfigLoader
from IPython.core import release
from IPython.core.iplib import InteractiveShell
from IPython.config.loader import (
    NoConfigDefault, 
    Config,
    ConfigError,
    PyFileConfigLoader
)

from IPython.lib import inputhook

from IPython.utils.ipstruct import Struct
from IPython.utils.genutils import filefind, get_ipython_dir

#-----------------------------------------------------------------------------
# Utilities and helpers
#-----------------------------------------------------------------------------


ipython_desc = """
A Python shell with automatic history (input and output), dynamic object
introspection, easier configuration, command completion, access to the system
shell and more.
"""

def pylab_warning():
    msg = """

IPython's -pylab mode has been disabled until matplotlib supports this version
of IPython.  This version of IPython has greatly improved GUI integration that 
matplotlib will soon be able to take advantage of.  This will eventually
result in greater stability and a richer API for matplotlib under IPython.
However during this transition, you will either need to use an older version
of IPython, or do the following to use matplotlib interactively::

    import matplotlib
    matplotlib.interactive(True)
    matplotlib.use('wxagg')  # adjust for your backend
    %gui -a wx               # adjust for your GUI
    from matplotlib import pyplot as plt

See the %gui magic for information on the new interface.
"""
    warnings.warn(msg, category=DeprecationWarning, stacklevel=1)


#-----------------------------------------------------------------------------
# Main classes and functions
#-----------------------------------------------------------------------------

cl_args = (
    (('-autocall',), dict(
        type=int, dest='InteractiveShell.autocall', default=NoConfigDefault,
        help='Set the autocall value (0,1,2).',
        metavar='InteractiveShell.autocall')
    ),
    (('-autoindent',), dict(
        action='store_true', dest='InteractiveShell.autoindent', default=NoConfigDefault,
        help='Turn on autoindenting.')
    ),
    (('-noautoindent',), dict(
        action='store_false', dest='InteractiveShell.autoindent', default=NoConfigDefault,
        help='Turn off autoindenting.')
    ),
    (('-automagic',), dict(
        action='store_true', dest='InteractiveShell.automagic', default=NoConfigDefault,
        help='Turn on the auto calling of magic commands.')
    ),
    (('-noautomagic',), dict(
        action='store_false', dest='InteractiveShell.automagic', default=NoConfigDefault,
        help='Turn off the auto calling of magic commands.')
    ),
    (('-autoedit_syntax',), dict(
        action='store_true', dest='InteractiveShell.autoedit_syntax', default=NoConfigDefault,
        help='Turn on auto editing of files with syntax errors.')
    ),
    (('-noautoedit_syntax',), dict(
        action='store_false', dest='InteractiveShell.autoedit_syntax', default=NoConfigDefault,
        help='Turn off auto editing of files with syntax errors.')
    ),
    (('-banner',), dict(
        action='store_true', dest='Global.display_banner', default=NoConfigDefault,
        help='Display a banner upon starting IPython.')
    ),
    (('-nobanner',), dict(
        action='store_false', dest='Global.display_banner', default=NoConfigDefault,
        help="Don't display a banner upon starting IPython.")
    ),
    (('-cache_size',), dict(
        type=int, dest='InteractiveShell.cache_size', default=NoConfigDefault,
        help="Set the size of the output cache.",
        metavar='InteractiveShell.cache_size')
    ),
    (('-classic',), dict(
        action='store_true', dest='Global.classic', default=NoConfigDefault,
        help="Gives IPython a similar feel to the classic Python prompt.")
    ),
    (('-colors',), dict(
        type=str, dest='InteractiveShell.colors', default=NoConfigDefault,
        help="Set the color scheme (NoColor, Linux, and LightBG).",
        metavar='InteractiveShell.colors')
    ),
    (('-color_info',), dict(
        action='store_true', dest='InteractiveShell.color_info', default=NoConfigDefault,
        help="Enable using colors for info related things.")
    ),
    (('-nocolor_info',), dict(
        action='store_false', dest='InteractiveShell.color_info', default=NoConfigDefault,
        help="Disable using colors for info related things.")
    ),
    (('-confirm_exit',), dict(
        action='store_true', dest='InteractiveShell.confirm_exit', default=NoConfigDefault,
        help="Prompt the user when existing.")
    ),
    (('-noconfirm_exit',), dict(
        action='store_false', dest='InteractiveShell.confirm_exit', default=NoConfigDefault,
        help="Don't prompt the user when existing.")
    ),
    (('-deep_reload',), dict(
        action='store_true', dest='InteractiveShell.deep_reload', default=NoConfigDefault,
        help="Enable deep (recursive) reloading by default.")
    ),
    (('-nodeep_reload',), dict(
        action='store_false', dest='InteractiveShell.deep_reload', default=NoConfigDefault,
        help="Disable deep (recursive) reloading by default.")
    ),
    (('-editor',), dict(
        type=str, dest='InteractiveShell.editor', default=NoConfigDefault,
        help="Set the editor used by IPython (default to $EDITOR/vi/notepad).",
        metavar='InteractiveShell.editor')
    ),
    (('-log','-l'), dict(
        action='store_true', dest='InteractiveShell.logstart', default=NoConfigDefault,
        help="Start logging to the default file (./ipython_log.py).")
    ),
    (('-logfile','-lf'), dict(
        type=str, dest='InteractiveShell.logfile', default=NoConfigDefault,
        help="Start logging to logfile.",
        metavar='InteractiveShell.logfile')
    ),
    (('-logappend','-la'), dict(
        type=str, dest='InteractiveShell.logappend', default=NoConfigDefault,
        help="Start logging to logappend in append mode.",
        metavar='InteractiveShell.logfile')
    ),
    (('-pdb',), dict(
        action='store_true', dest='InteractiveShell.pdb', default=NoConfigDefault,
        help="Enable auto calling the pdb debugger after every exception.")
    ),
    (('-nopdb',), dict(
        action='store_false', dest='InteractiveShell.pdb', default=NoConfigDefault,
        help="Disable auto calling the pdb debugger after every exception.")
    ),
    (('-pprint',), dict(
        action='store_true', dest='InteractiveShell.pprint', default=NoConfigDefault,
        help="Enable auto pretty printing of results.")
    ),
    (('-nopprint',), dict(
        action='store_false', dest='InteractiveShell.pprint', default=NoConfigDefault,
        help="Disable auto auto pretty printing of results.")
    ),
    (('-prompt_in1','-pi1'), dict(
        type=str, dest='InteractiveShell.prompt_in1', default=NoConfigDefault,
        help="Set the main input prompt ('In [\#]: ')",
        metavar='InteractiveShell.prompt_in1')
    ),
    (('-prompt_in2','-pi2'), dict(
        type=str, dest='InteractiveShell.prompt_in2', default=NoConfigDefault,
        help="Set the secondary input prompt (' .\D.: ')",
        metavar='InteractiveShell.prompt_in2')
    ),
    (('-prompt_out','-po'), dict(
        type=str, dest='InteractiveShell.prompt_out', default=NoConfigDefault,
        help="Set the output prompt ('Out[\#]:')",
        metavar='InteractiveShell.prompt_out')
    ),
    (('-quick',), dict(
        action='store_true', dest='Global.quick', default=NoConfigDefault,
        help="Enable quick startup with no config files.")
    ),
    (('-readline',), dict(
        action='store_true', dest='InteractiveShell.readline_use', default=NoConfigDefault,
        help="Enable readline for command line usage.")
    ),
    (('-noreadline',), dict(
        action='store_false', dest='InteractiveShell.readline_use', default=NoConfigDefault,
        help="Disable readline for command line usage.")
    ),
    (('-screen_length','-sl'), dict(
        type=int, dest='InteractiveShell.screen_length', default=NoConfigDefault,
        help='Number of lines on screen, used to control printing of long strings.',
        metavar='InteractiveShell.screen_length')
    ),
    (('-separate_in','-si'), dict(
        type=str, dest='InteractiveShell.separate_in', default=NoConfigDefault,
        help="Separator before input prompts.  Default '\n'.",
        metavar='InteractiveShell.separate_in')
    ),
    (('-separate_out','-so'), dict(
        type=str, dest='InteractiveShell.separate_out', default=NoConfigDefault,
        help="Separator before output prompts.  Default 0 (nothing).",
        metavar='InteractiveShell.separate_out')
    ),
    (('-separate_out2','-so2'), dict(
        type=str, dest='InteractiveShell.separate_out2', default=NoConfigDefault,
        help="Separator after output prompts.  Default 0 (nonight).",
        metavar='InteractiveShell.separate_out2')
    ),
    (('-nosep',), dict(
        action='store_true', dest='Global.nosep', default=NoConfigDefault,
        help="Eliminate all spacing between prompts.")
    ),
    (('-term_title',), dict(
        action='store_true', dest='InteractiveShell.term_title', default=NoConfigDefault,
        help="Enable auto setting the terminal title.")
    ),
    (('-noterm_title',), dict(
        action='store_false', dest='InteractiveShell.term_title', default=NoConfigDefault,
        help="Disable auto setting the terminal title.")
    ),
    (('-xmode',), dict(
        type=str, dest='InteractiveShell.xmode', default=NoConfigDefault,
        help="Exception mode ('Plain','Context','Verbose')",
        metavar='InteractiveShell.xmode')
    ),
    (('-ext',), dict(
        type=str, dest='Global.extra_extension', default=NoConfigDefault,
        help="The dotted module name of an IPython extension to load.",
        metavar='Global.extra_extension')
    ),
    (('-c',), dict(
        type=str, dest='Global.code_to_run', default=NoConfigDefault,
        help="Execute the given command string.",
        metavar='Global.code_to_run')
    ),
    (('-i',), dict(
        action='store_true', dest='Global.force_interact', default=NoConfigDefault,
        help="If running code from the command line, become interactive afterwards.")
    ),
    (('-wthread',), dict(
        action='store_true', dest='Global.wthread', default=NoConfigDefault,
        help="Enable wxPython event loop integration.")
    ),
    (('-q4thread','-qthread'), dict(
        action='store_true', dest='Global.q4thread', default=NoConfigDefault,
        help="Enable Qt4 event loop integration. Qt3 is no longer supported.")
    ),
    (('-gthread',), dict(
        action='store_true', dest='Global.gthread', default=NoConfigDefault,
        help="Enable GTK event loop integration.")
    ),
    # # These are only here to get the proper deprecation warnings
    (('-pylab',), dict(
        action='store_true', dest='Global.pylab', default=NoConfigDefault,
        help="Disabled.  Pylab has been disabled until matplotlib supports this version of IPython.")
    )
)


class IPythonAppCLConfigLoader(IPythonArgParseConfigLoader):

    arguments = cl_args


_default_config_file_name = 'ipython_config.py'

class IPythonApp(Application):
    name = 'ipython'
    config_file_name = _default_config_file_name

    def create_default_config(self):
        super(IPythonApp, self).create_default_config()
        self.default_config.Global.display_banner = True
        
        # If the -c flag is given or a file is given to run at the cmd line
        # like "ipython foo.py", normally we exit without starting the main
        # loop.  The force_interact config variable allows a user to override
        # this and interact.  It is also set by the -i cmd line flag, just
        # like Python.
        self.default_config.Global.force_interact = False

        # By default always interact by starting the IPython mainloop.
        self.default_config.Global.interact = True

        # Let the parent class set the default, but each time log_level
        # changes from config, we need to update self.log_level as that is
        # what updates the actual log level in self.log.
        self.default_config.Global.log_level = self.log_level

        # No GUI integration by default
        self.default_config.Global.wthread = False
        self.default_config.Global.q4thread = False
        self.default_config.Global.gthread = False

    def create_command_line_config(self):
        """Create and return a command line config loader."""
        return IPythonAppCLConfigLoader(
            description=ipython_desc,
            version=release.version)

    def post_load_command_line_config(self):
        """Do actions after loading cl config."""
        clc = self.command_line_config

        # Display the deprecation warnings about threaded shells
        if hasattr(clc.Global, 'pylab'):
            pylab_warning()
            del clc.Global['pylab']

    def load_file_config(self):
        if hasattr(self.command_line_config.Global, 'quick'):
            if self.command_line_config.Global.quick:
                self.file_config = Config()
                return
        super(IPythonApp, self).load_file_config()

    def post_load_file_config(self):
        if hasattr(self.command_line_config.Global, 'extra_extension'):
            if not hasattr(self.file_config.Global, 'extensions'):
                self.file_config.Global.extensions = []
            self.file_config.Global.extensions.append(
                self.command_line_config.Global.extra_extension)
            del self.command_line_config.Global.extra_extension

    def pre_construct(self):
        config = self.master_config

        if hasattr(config.Global, 'classic'):
            if config.Global.classic:
                config.InteractiveShell.cache_size = 0
                config.InteractiveShell.pprint = 0
                config.InteractiveShell.prompt_in1 = '>>> '
                config.InteractiveShell.prompt_in2 = '... '
                config.InteractiveShell.prompt_out = ''
                config.InteractiveShell.separate_in = \
                    config.InteractiveShell.separate_out = \
                    config.InteractiveShell.separate_out2 = ''
                config.InteractiveShell.colors = 'NoColor'
                config.InteractiveShell.xmode = 'Plain'

        if hasattr(config.Global, 'nosep'):
            if config.Global.nosep:
                config.InteractiveShell.separate_in = \
                config.InteractiveShell.separate_out = \
                config.InteractiveShell.separate_out2 = ''

        # if there is code of files to run from the cmd line, don't interact
        # unless the -i flag (Global.force_interact) is true.
        code_to_run = config.Global.get('code_to_run','')
        file_to_run = False
        if len(self.extra_args)>=1:
            if self.extra_args[0]:
                file_to_run = True
        if file_to_run or code_to_run:
            if not config.Global.force_interact:
                config.Global.interact = False

    def construct(self):
        # I am a little hesitant to put these into InteractiveShell itself.
        # But that might be the place for them
        sys.path.insert(0, '')

        # Create an InteractiveShell instance
        self.shell = InteractiveShell(
            parent=None,
            config=self.master_config
        )

    def post_construct(self):
        """Do actions after construct, but before starting the app."""
        config = self.master_config
        
        # shell.display_banner should always be False for the terminal 
        # based app, because we call shell.show_banner() by hand below
        # so the banner shows *before* all extension loading stuff.
        self.shell.display_banner = False

        if config.Global.display_banner and \
            config.Global.interact:
            self.shell.show_banner()

        # Make sure there is a space below the banner.
        if self.log_level <= logging.INFO: print

        # Now a variety of things that happen after the banner is printed.
        self._enable_gui()
        self._load_extensions()
        self._run_exec_lines()
        self._run_exec_files()
        self._run_cmd_line_code()

    def _enable_gui(self):
        """Enable GUI event loop integration."""
        config = self.master_config
        try:
            # Enable GUI integration
            if config.Global.wthread:
                self.log.info("Enabling wx GUI event loop integration")
                inputhook.enable_wx(app=True)
            elif config.Global.q4thread:
                self.log.info("Enabling Qt4 GUI event loop integration")
                inputhook.enable_qt4(app=True)
            elif config.Global.gthread:
                self.log.info("Enabling GTK GUI event loop integration")
                inputhook.enable_gtk(app=True)
        except:
            self.log.warn("Error in enabling GUI event loop integration:")
            self.shell.showtraceback()

    def _load_extensions(self):
        """Load all IPython extensions in Global.extensions.

        This uses the :meth:`InteractiveShell.load_extensions` to load all
        the extensions listed in ``self.master_config.Global.extensions``.
        """
        try:
            if hasattr(self.master_config.Global, 'extensions'):
                self.log.debug("Loading IPython extensions...")
                extensions = self.master_config.Global.extensions
                for ext in extensions:
                    try:
                        self.log.info("Loading IPython extension: %s" % ext)                        
                        self.shell.load_extension(ext)
                    except:
                        self.log.warn("Error in loading extension: %s" % ext)
                        self.shell.showtraceback()
        except:
            self.log.warn("Unknown error in loading extensions:")
            self.shell.showtraceback()

    def _run_exec_lines(self):
        """Run lines of code in Global.exec_lines in the user's namespace."""
        try:
            if hasattr(self.master_config.Global, 'exec_lines'):
                self.log.debug("Running code from Global.exec_lines...")
                exec_lines = self.master_config.Global.exec_lines
                for line in exec_lines:
                    try:
                        self.log.info("Running code in user namespace: %s" % line)
                        self.shell.runlines(line)
                    except:
                        self.log.warn("Error in executing line in user namespace: %s" % line)
                        self.shell.showtraceback()
        except:
            self.log.warn("Unknown error in handling Global.exec_lines:")
            self.shell.showtraceback()

    def _exec_file(self, fname):
        full_filename = filefind(fname, ['.', self.ipythondir])
        if os.path.isfile(full_filename):
            if full_filename.endswith('.py'):
                self.log.info("Running file in user namespace: %s" % full_filename)
                self.shell.safe_execfile(full_filename, self.shell.user_ns)
            elif full_filename.endswith('.ipy'):
                self.log.info("Running file in user namespace: %s" % full_filename)
                self.shell.safe_execfile_ipy(full_filename)
            else:
                self.log.warn("File does not have a .py or .ipy extension: <%s>" % full_filename)

    def _run_exec_files(self):
        try:
            if hasattr(self.master_config.Global, 'exec_files'):
                self.log.debug("Running files in Global.exec_files...")
                exec_files = self.master_config.Global.exec_files
                for fname in exec_files:
                    self._exec_file(fname)
        except:
            self.log.warn("Unknown error in handling Global.exec_files:")
            self.shell.showtraceback()

    def _run_cmd_line_code(self):
        if hasattr(self.master_config.Global, 'code_to_run'):
            line = self.master_config.Global.code_to_run
            try:
                self.log.info("Running code given at command line (-c): %s" % line)
                self.shell.runlines(line)
            except:
                self.log.warn("Error in executing line in user namespace: %s" % line)
                self.shell.showtraceback()
            return
        # Like Python itself, ignore the second if the first of these is present
        try:
            fname = self.extra_args[0]
        except:
            pass
        else:
            try:
                self._exec_file(fname)
            except:
                self.log.warn("Error in executing file in user namespace: %s" % fname)
                self.shell.showtraceback()

    def start_app(self):
        if self.master_config.Global.interact:
            self.log.debug("Starting IPython's mainloop...")
            self.shell.mainloop()


def load_default_config(ipythondir=None):
    """Load the default config file from the default ipythondir.

    This is useful for embedded shells.
    """
    if ipythondir is None:
        ipythondir = get_ipython_dir()
    cl = PyFileConfigLoader(_default_config_file_name, ipythondir)
    config = cl.load_config()
    return config


def launch_new_instance():
    """Create a run a full blown IPython instance"""
    app = IPythonApp()
    app.start()

