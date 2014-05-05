#!/usr/bin/env python
"""Trimming of trailing white spaces.

Author-email: "Dietmar Winkler" <dietmar.winkler@dwe.no>

License: See UNLICENSE file

This script will recursively remove all trailing white spaces in all
text files in a given directory. Binary files and files residing in
version control specific directories are skipped.

As an addition one can also let it clean out obsolete or empty/superfluous
Modelica annotations from Modelica (`*.mo`) files.

It uses a binary tester based on the python magic implementation from
    Adam Hupp, http://hupp.org/adam/hg/python-magic

As a fallback (especially if libmagic is not available, like on Windows)
it acts only on files with a given file extension listed in 'extstring'.

"""
from __future__ import absolute_import, with_statement

import os
import textwrap
import io

from pyparsing import (White, Keyword, nestedExpr, lineEnd, Suppress,
                       ZeroOrMore, Optional, CharsNotIn, ParseException,
                       CaselessLiteral)


# For Windows: list of file extensions to apply the script on
# (including the dot and separated by a comma)
extstring = ".mo,.mos,.c,.h,.cpp,.txt,.order"

# list of version control directories to ignore
BLACKLIST = ['.bzr', '.cvs', '.git', '.hg', '.svn', '.#']

# convert the string object to a list object
listofexts  = extstring.split(",")

def unknownOption(script_name, args):
    """Warning message for unknown options."""
    warning = """
        UNKNOWN OPTION: "%s"

        Use %s -h [--help] for usage instructions.
        """ % (args,script_name,)
    print textwrap.dedent(warning)

def unknownDirectory(args):
    """Warning message for unknown Directory."""
    warning = """
        WARNING: Ignoring unkown directory: "%s"
        """ % (args)
    print textwrap.dedent(warning)

def detecttype(filepath):
    """Detect the mime type of the text file."""
    try:
        from .magic import Magic
        mime = Magic(mime=True)
        type = mime.from_file(filepath)
        root, ext = os.path.splitext(filepath)
        if ext in '.mo':
            return "mo"
        elif "text/" in type:
            return "text"
        else:
            return type
    except (ImportError, TypeError):
        root, ext = os.path.splitext(filepath)
        if ext in '.mo':
            return "mo"
        elif ext in listofexts:
            return "text"
        else:
            return "unknown"

def trimWhitespace(filepath, eol):
    """Trim trailing white spaces from a given filepath."""
    try:
        with io.open(filepath, "r") as source:
            lines = [line.rstrip() for line in source]
        with io.open(filepath, "w", newline=eol) as target:
            target.write("\n".join(lines) + "\n")
    except (UnicodeDecodeError, TypeError) as inst:
        print("\nOops! Failing to process file: %s\n"
              "Are you sure it is of pure ASCII or UTF8 encoding?\n" % source.name)
        raise

def flatten(arg):
      ret = []
      for item in arg:
        if type(item)==list:
          ret = ret + flatten(item)
        elif type(item)==tuple:
          ret = ret + flatten(list(item))
        else:
          ret.append(item)
      return ret

def skipNonEmptyGraphics(s, loc, tokens):
    flattened =  flatten(tokens.args[0].asList())
    graphicsPresent = False
    for substring in flattened:
        if (substring.startswith('graphics')
            or substring.startswith(',graphics')
            or not substring.startswith('extent={{-100,-100},{100,100}}')):
                if not ('graphics' or ',graphics') in flattened[-1]:
                    graphicsPresent = True
    if graphicsPresent:
        raise ParseException('graphics defined, skipping...')

def cleanAnnotation(filepath, eol):
    """Clean out the obsolete or superflous annotations."""
    with io.open(filepath, 'r') as mo_file:
        string = mo_file.read()
        # remove old Modelica 1 'Window(),' and 'Coordsys()' annotations:
        WindowRef = ZeroOrMore(White(' \t')) + (Keyword('Window')|Keyword('Coordsys')) + nestedExpr() + ',' + ZeroOrMore(White(' \t') + lineEnd)
        out = Suppress(WindowRef).transformString(string)
        # special care needs to be taken if the annotation is the last one
        WindowLastRef = Optional(',') + ZeroOrMore(White(' \t')) + (Keyword('Window')|Keyword('Coordsys')) + nestedExpr() + ZeroOrMore(White(' \t') + lineEnd)
        out = Suppress(WindowLastRef).transformString(out)

        # remove empty and superfluous Dymola specific annotations:
        dymolaRef = (ZeroOrMore(White(' \t'))
                     + ((Optional('__Dymola_') + 'experimentSetupOutput')|
                        Keyword('DymolaStoredErrors'))
                     + ~nestedExpr() + ',' + ZeroOrMore(White(' \t')))
        out = Suppress(dymolaRef).transformString(out)
        # special care of the last one again
        lastDymolaRef = (Optional(',') + ZeroOrMore(White(' \t'))
                         + ((Optional('__Dymola_') + 'experimentSetupOutput')|
                            Keyword('DymolaStoredErrors'))
                         + ~nestedExpr() + ZeroOrMore(White(' \t')))
        out = Suppress(lastDymolaRef).transformString(out)

        # remove superfluous annotations with defaults
        defaultRef = ((Keyword('rotation')|Keyword('visible')|Keyword('origin'))
                      + ZeroOrMore(White(' \t')) + '=' + ZeroOrMore(White(' \t'))
                      + (Keyword('0')|Keyword('true')|Keyword('{0,0}'))
                      + ',' + ZeroOrMore(White(' \t')))
        out = Suppress(defaultRef).transformString(out)
        # special rule for initial scale in order to avoid false positives
        iniSRef = (Keyword('initialScale')
                   + ZeroOrMore(White(' \t')) + '=' + ZeroOrMore(White(' \t'))
                   + Keyword('0.1')
                   + ',' + ZeroOrMore(White(' \t')))
        out = Suppress(iniSRef).transformString(out)
        # special care for the last ones again
        lastDefaultRef = (Optional(',')
                          + (Keyword('rotation')|Keyword('visible')|Keyword('origin'))
                          + ZeroOrMore(White(' \t')) + '=' + ZeroOrMore(White(' \t'))
                          + (Keyword('0')|Keyword('true')|Keyword('{0,0}'))
                          + ZeroOrMore(White(' \t')))
        out = Suppress(lastDefaultRef).transformString(out)
        lastIniSRef = (Optional(',') + Keyword('initialScale')
                       + ZeroOrMore(White(' \t')) + '=' + ZeroOrMore(White(' \t'))
                       + Keyword('0.1')
                       + ZeroOrMore(White(' \t')))
        out = Suppress(lastIniSRef).transformString(out)

        # remove Icon and Diagram annotations that do not contain any graphics
        emptyRef =  ZeroOrMore(White(' \t')) + (Keyword('Icon')|Keyword('Diagram')) + nestedExpr()('args') + ',' + ZeroOrMore(White(' \t') + lineEnd)
        emptyRef.setParseAction(skipNonEmptyGraphics)
        out = Suppress(emptyRef).transformString(out)
        # special care for the last annotation again
        lastEmptyRef =   Optional(',') + ZeroOrMore(White(' \t')) + (Keyword('Icon')|Keyword('Diagram')) + nestedExpr()('args') + ZeroOrMore(White(' \t') + lineEnd)
        lastEmptyRef.setParseAction(skipNonEmptyGraphics)
        out = Suppress(lastEmptyRef).transformString(out)

        # in case we end up with empty annotations remove them too
        AnnotationRef = ZeroOrMore(White(' \t')) + Keyword('annotation') + nestedExpr('(',');',content=' ') + ZeroOrMore(White(' \t') + lineEnd)
        out = Suppress(AnnotationRef).transformString(out)
    with io.open(filepath,'w', newline= eol) as mo_file:
        mo_file.write(out)

def stripDocString(filepath, eol):
    """Strip spaces between string start/end and tag"""
    with io.open(filepath, 'r') as mo_file:
        string = mo_file.read()

        # define expressions to match leading and trailing
        # html tags, and just suppress the leading or trailing whitespace
        opener = White().suppress() + CaselessLiteral("<html>")
        closer = CaselessLiteral("</html>") + White().suppress()

        # define a single expression to match either opener
        # or closer - have to add leaveWhitespace() call so that
        # we catch the leading whitespace in opener
        either = opener|closer
        either.leaveWhitespace()
        out = either.transformString(string)

    with io.open(filepath, 'w', newline=eol) as mo_file:
        mo_file.write(out)
