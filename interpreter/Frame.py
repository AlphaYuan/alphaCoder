import collections

import six

# from interpreter.Stack import Stack


class Cell(object):

    def __init__(self, val):
        self.contents = val
        
    def get(self):
        return self.contents
    
    def set(self, val):
        self.contents = val


Block = collections.namedtuple("Block", "type, handler, level")


class Frame(object):

    def __init__(self, f_code, f_globals, f_locals, f_back):
        self.stack = []
        self.f_code = f_code
        self.f_globals = f_globals
        self.f_locals = f_locals
        self.f_back = f_back
        if f_back:
            self.f_builtins = f_back.f_builtins
        else:
            self.f_builtins = f_locals['__builtins__']
            if hasattr(self.f_builtins, '__dict__'):
                self.f_builtins = self.f_builtins.__dict__

        self.f_line_no = f_code.co_firstlineno
        self.f_lasti = 0

        if f_code.co_cellvars:
            self.cells = {}
            if not f_back.cells:
                f_back.cells = {}
            for var in f_code.co_cellvars:
                cell = Cell(self.f_locals.get(var))
                self.cells = f_back.cells[var] = cell
        else:
            self.cells = None

        if f_code.co_freevars:
            if not self.cells:
                self.cells = {}
            for var in f_code.co_freevars:
                assert self.cells is not None
                assert f_back.cells, 'f_back.cells: %r' % (f_back.cells, )
                self.cells[var] = f_back.cells[var]

        self.block_stack = []
        self.generator = None

    def __repr__(self):
        return '<Frame at 0x%08x: %r @ %d>' % (id(self), self.f_code.co_filename, self.f_line_no)

    def line_number(self):
        line_no_tab = self.f_code.co_lnotab
        byte_increments = six.iterbytes(line_no_tab[0::2])
        line_increments = six.iterbytes(line_no_tab[1::2])

        byte_num = 0
        line_num = self.f_code.co_firstlineno

        for byte_incr, line_incr in zip(byte_increments, line_increments):
            byte_num += byte_incr
            if byte_num > self.f_lasti:
                break
            line_num += line_incr

        return line_num

