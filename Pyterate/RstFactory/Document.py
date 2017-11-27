####################################################################################################
#
# Pyterate - Sphinx add-ons to create API documentation for Python projects
# Copyright (C) 2014 Fabrice Salvaire
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
#
####################################################################################################

####################################################################################################

import logging
import os
import tempfile

from ..Jupyter import JupyterClient
from ..Template import TemplateAggregator
from ..Tools.Path import remove_extension
from ..Tools.Timestamp import timestamp
from .Dom import *

# Load default extensions
from .FigureGenerator.Registry import ExtensionMetaclass

####################################################################################################

_module_logger = logging.getLogger(__name__)

####################################################################################################

SETUP_CODE = '''
from Pyterate.RstFactory.Tools import save_figure
'''

####################################################################################################

class Document:

    """ This class is responsible to process an document. """

    _logger = _module_logger.getChild('Document')

    FIGURE_MARKUPS = ['fig', 'lfig', 'i', 'itxt', 'o']
    FIGURE_MARKUPS += ExtensionMetaclass.extension_markups()

    FIGURE_MAP = {
        'fig':  FigureChunk,
        'i':    PythonIncludeChunk,
        'itxt': LiteralIncludeChunk,
        'lfig': LocaleFigureChunk,
        'o':    OutputChunk,
    }
    FIGURE_MAP.update({markup:cls for markup, cls in ExtensionMetaclass.iter()})

    ##############################################

    def __init__(self, topic, filename):

        self._topic = topic
        self._basename = remove_extension(filename) # input basename

        path = topic.join_path(filename)
        self._is_link = os.path.islink(path)
        self._path = os.path.realpath(path) # input path

        if self._is_link:
            factory = self.factory
            path = factory.join_rst_document_path(os.path.relpath(self._path, factory.documents_path))
            self._rst_path = remove_extension(path) + '.rst'
        else:
            self._rst_path = self._topic.join_rst_path(self.rst_filename)

    ##############################################

    @property
    def topic(self):
        return self._topic

    @property
    def topic_path(self):
        return self._topic.path

    @property
    def topic_rst_path(self):
        return self._topic.rst_path

    @property
    def factory(self):
        return self._topic.factory

    @property
    def path(self):
        return self._path

    @property
    def basename(self):
        return self._basename

    @property
    def rst_filename(self):
        return self._basename + '.rst'

    @property
    def rst_inner_path(self):
        return os.path.sep + os.path.relpath(self._rst_path, self.factory.rst_source_path)

    ##############################################

    @property
    def is_link(self):
        return self._is_link

    ##############################################

    def read(self):

        # Fixme: API ??? called process_document()

        # Must be called first !

        with open(self._path) as fh:
            self._source = fh.readlines()
        self._parse_source()

    ##############################################

    @property
    def source_timestamp(self):
        return timestamp(self._path)

    ##############################################

    @property
    def rst_timestamp(self):

        if os.path.exists(self._rst_path):
            return timestamp(self._rst_path)
        else:
            return -1

    ##############################################

    def __bool__(self):
        """Return True if source is older than rst."""
        return self.source_timestamp > self.rst_timestamp

    ##############################################

    def run_code(self):

        self._logger.info("\nRun document " + self._path)

        has_error = False
        with tempfile.TemporaryDirectory() as working_directory:
            jupyter_client = JupyterClient(working_directory)
            jupyter_client.run_cell(SETUP_CODE)
            for chunk in self._dom.iter_on_code_chunks():
                code = chunk.to_python()
                self._logger.debug('Execute\n{}'.format(code))
                outputs = jupyter_client.run_cell(code)
                if outputs:
                    output = outputs[0]
                    self._logger.debug('Output {0.output_type}\n{0}'.format(output))
                    chunk.outputs = outputs
                for output in outputs:
                    if output.is_error and not chunk.guarded:
                        has_error = True
                        self._logger.error("Error in document {}\n".format(self._path) + str(output))

        if has_error:
            self._logger.error("Failed to run document {}".format(self._path))
            self.factory.register_failure(self)

    ##############################################

    def make_external_figure(self, force):

        for chunck in self._dom:
            if isinstance(chunck, ExtensionMetaclass.extensions()):
                if force or chunck:
                    chunck.make_figure()

    ##############################################

    def _append_rst_chunck(self):

        # if self._rst_chunck:
        chunk = self._rst_chunck
        if chunk.has_format():
            chunk = chunk.to_rst_format_chunk()
        self._dom.append(chunk)
        self._rst_chunck = RstChunk()

    ##############################################

    def _append_literal_chunck(self):

        # if self._literal_chunck:
        chunk = self._literal_chunck
        self._dom.append(chunk)
        self._literal_chunck = LiteralChunk()

    ##############################################

    def _append_code_chunck(self, hidden=False):

        if self._code_chunck:
            self._logger.debug('append code chunk, guarded {} interactive {}'.format(self._code_chunck.guarded, self._in_interactive_code))
            chunck = self._code_chunck
            if self._in_interactive_code:
                for subchunck in chunck.to_interactive():
                    self._dom.append(subchunck)
            else:
                self._dom.append(chunck)

        if hidden:
            self._code_chunck = HiddenCodeChunk()
        else:
            self._code_chunck = CodeChunk()

    ##############################################

    def _append_last_chunck(self, rst=False, literal=False, code=False):

        if rst and self._rst_chunck:
            self._append_rst_chunck()
        elif literal and self._literal_chunck:
            self._append_literal_chunck()
        elif code and self._code_chunck:
            self._append_code_chunck()

    ##############################################

    def _line_start_by_markup(self, line, markup):

        return line.startswith('#{}#'.format(markup))

    ##############################################

    def _line_starts_by_figure_markup(self, line):

        for markup in self.FIGURE_MARKUPS:
            if self._line_start_by_markup(line, markup):
                return True
        return False

    ##############################################

    def _check_enter_state(self):

        if self._in_guarded_code or self._in_interactive_code:
            self._logger.warning("interleaved markup")
            return False
        else:
            # Note: rst case is handled in parser
            self._append_code_chunck()
            return True

    ##############################################

    def _check_leave_state(self):

        if self._in_guarded_code or self._in_interactive_code:
            # Note: rst case is handled in parser
            self._append_code_chunck()
            return True
        else:
            self._logger.warning("missing enter markup")
            return False

    ##############################################

    def _parse_source(self):

        """Parse the Python source code and extract chunks of codes, RST contents, plot and Tikz figures.
        The source code is annoted using comment lines starting with special directives of the form
        *#directive name#*.  RST content lines start with *#!#*.  We can include a figure using
        *#lfig#*, a figure generated by matplotlib using the directive *#fig#*, tikz figure using
        *#tz#* and the content of a file using *#itxt#* and *#i#* for Python source.  Comment that
        must be skipped start with *#?#*.  Hidden Python code start with *#h#*.  The directive *#o#*
        is used to split the output and to instruct to include the previous chunk.  RST content can
        be formatted with variable from the locals dictionary using *@<@...@>@* instead of *{...}*.

        """

        self._dom = Dom()
        self._rst_chunck = RstChunk()
        self._literal_chunck = LiteralChunk()
        self._code_chunck = CodeChunk()

        self._in_guarded_code = False
        self._in_interactive_code = False

        # Use a while loop trick to remove consecutive blank lines
        number_of_lines = len(self._source)
        i = 0
        while i < number_of_lines:
            line = self._source[i]
            self._logger.debug('\n' + line.rstrip())
            i += 1
            remove_next_blanck_line = True

            # Handle comments
            if (self._line_start_by_markup(line, '?')
                or line.startswith('#'*10) # long rule # Fixme: hardcoded !
                or line.startswith(' '*4 + '#'*10)): # short rule
                pass

            # Handle figures
            elif self._line_starts_by_figure_markup(line):
                self._append_last_chunck(rst=True, literal=True, code=True)
                if self._line_start_by_markup(line, 'o'):
                    if not self._dom.last_chunk.is_executed:
                        self._logger.error('Previous chunk must be code') # Fixme: handle
                    self._dom.append(OutputChunk(self._dom.last_chunk))
                else:
                    for markup, cls in self.FIGURE_MAP.items():
                        if self._line_start_by_markup(line, markup):
                            print(cls, line)
                            self._dom.append(cls(self, line))
                            break

            # Handle RST contents
            elif self._line_start_by_markup(line, '!'):
                self._append_last_chunck(literal=True, code=True)
                self._rst_chunck.append(line)

            # Handle literal contents
            elif self._line_start_by_markup(line, 'l'):
                self._append_last_chunck(rst=True, code=True)
                self._literal_chunck.append(line)

            elif self._line_start_by_markup(line, '<e'):
                if self._check_enter_state():
                    self._code_chunck.guarded = True
                    self._in_guarded_code = True
            elif self._line_start_by_markup(line, 'e>'):
                if self._check_leave_state():
                    self._in_guarded_code = False

            elif self._line_start_by_markup(line, '<i'):
                if self._check_enter_state():
                    self._in_interactive_code = True
            elif self._line_start_by_markup(line, 'i>'):
                if self._check_leave_state():
                    self._in_interactive_code = False

            # Handle Python codes
            else:
                # if line.startswith('pylab.show()'):
                #     continue
                remove_next_blanck_line = False
                self._append_last_chunck(rst=True, literal=True)
                if self._line_start_by_markup(line, 'h') and isinstance(self._code_chunck, CodeChunk):
                    self._append_code_chunck(hidden=True)
                elif isinstance(self._code_chunck, HiddenCodeChunk):
                    self._append_code_chunck()
                self._code_chunck.append(line)

            # Fixme: ???
            if remove_next_blanck_line and i < number_of_lines and not self._source[i].strip():
                i += 1

        # Append remaining chunck
        self._append_last_chunck(rst=True, literal=True, code=True)

    ##############################################

    def _has_title(self):

        """Return whether a title is defined."""

        # Fixme: test if first chunck ?
        for chunck in self._dom:
            if isinstance(chunck, RstChunk):
                content = str(chunck)
                if '='*(3+2) in content: # Fixme: hardcoded !
                    return True

        return False

    ##############################################

    def make_rst(self):

        """ Generate the document RST file. """

        self._logger.info("\nCreate RST file " + self._rst_path)

        # place the Python file in the rst path
        python_file_name = self._basename + '.py'
        link_path = self._topic.join_rst_path(python_file_name)
        if not os.path.exists(link_path):
            os.symlink(self._path, link_path)

        kwargs = {
            'python_file':python_file_name,
        }

        has_title = self._has_title()
        if not has_title:
            kwargs['title'] = self._basename.replace('-', ' ').title() # Fixme: Capitalize of

        template_aggregator = TemplateAggregator(self.factory.template_environment)
        template_aggregator.append('document', **kwargs)

        with open(self._rst_path, 'w') as fh:
            fh.write(str(template_aggregator))
            for chunck in self._dom:
                fh.write(str(chunck))
