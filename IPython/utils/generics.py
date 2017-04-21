"""Generic functions for extending IPython.

See http://cheeseshop.python.org/pypi/simplegeneric.

Here is an example from genutils.py::

    def print_lsstring(arg):
        "Prettier (non-repr-like) and more informative printer for LSString"
        print "LSString (.p, .n, .l, .s available). Value:"
        print arg
        
    print_lsstring = result_display.when_type(LSString)(print_lsstring)
"""

from IPython.core.error import TryNext
from IPython.external.simplegeneric import generic

@generic
def result_display(result):
    """Print the result of computation."""
    raise TryNext

@generic
def inspect_object(obj):
    """Called when you do obj?"""
    raise TryNext

@generic
def complete_object(obj, prev_completions):
    """Custom completer dispatching for python objects.

    Parameters
    ----------
    obj : object
        The object to complete.
    prev_completions : list
        List of attributes discovered so far.

    This should return the list of attributes in obj. If you only wish to
    add to the attributes already discovered normally, return 
    own_attrs + prev_completions.
    """
    raise TryNext
