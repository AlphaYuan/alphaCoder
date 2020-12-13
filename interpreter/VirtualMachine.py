import dis
import operator
import sys
import builtins

import six
from six.moves import reprlib

# from interpreter.Frame import Frame, Block
# from interpreter.Function import Function, Method, Generator
from Frame import Frame, Block
from Function import Function, Method, Generator

byteint = lambda b: b

repr_obj = reprlib.Repr()
repr_obj.maxother = 120
repper = repr_obj.repr


class VirtualMachineError(Exception):
    pass


class VirtualMachine(object):

    def __init__(self):
        self.frames = []
        self.frame = None
        self.return_value = None
        self.last_exception = None

    def run_code(self, code, f_globals=None, f_locals=None):
        # 执行编译后的字节码
        frame = self.make_frame(code, f_globals=f_globals, f_locals=f_locals)  # 创建Frame
        val = self.run_frame(frame)  # 运行Frame

        if self.frames:  # 执行完还有Frame剩下
            raise VirtualMachineError('Frames left over!')
        if self.frame and self.frame.stack:  # 还有数据没有弹出栈
            raise VirtualMachineError('Data left on stack! %r' % self.frame.stack)

        return val

    def make_frame(self, code, callargs={}, f_globals=None, f_locals=None):
        # 创建Frame
        if f_globals is not None and f_locals is None:
            f_locals = f_globals  # 全局变量和局部变量赋值
        elif self.frames:
            f_globals = self.frame.f_globals
            f_locals = {}
        else:
            f_globals = f_locals = {
                '__builtins__': __builtins__,
                '__name__': '__main__',
                '__doc__': None,
                '_package__': None,
            }
        f_locals.update(callargs)
        frame = Frame(code, f_globals, f_locals, self.frame)

        return frame

    def run_frame(self, frame):
        # 执行Frame
        self.push_frame(frame)

        while True:
            instruction, arguments, offset = self.parse_byte_and_args()  # 解析字节码，获得指令、参数和偏移量

            why = self.dispatch(instruction, arguments)  # 执行字节码，获得返回值
            if why == 'exception':
                pass
            if why == 'reraise':
                why = 'exception'
            if why != 'yield':
                while why and frame.block_stack:
                    why = self.manage_block_stack(why)
            if why:
                break

        self.pop_frame()  # 弹出Frame

        if why == 'exception':
            six.reraise(*self.last_exception)

        return self.return_value

    def parse_byte_and_args(self):
        frame = self.frame
        offset = frame.f_lasti
        byte_code = byteint(frame.f_code.co_code[offset])
        frame.f_lasti += 1
        byte_name = dis.opname[byte_code]
        # arg = None
        # arguments = []
        if byte_code >= dis.HAVE_ARGUMENT:
            arg = frame.f_code.co_code[frame.f_lasti: frame.f_lasti + 2]
            frame.f_lasti += 2
            arg_val = byteint(arg[0]) + (byteint(arg[1]) << 8) # arg[0]
            if byte_code in dis.hasconst:
                arg = frame.f_code.co_consts[arg_val]
            elif byte_code in dis.hasfree:
                if arg_val < len(frame.f_code.co_cellvars):
                    arg = frame.f_code.co_cellvars[arg_val]
                else:
                    var_idx = arg_val - len(frame.f_code.co_cellvars)
                    arg = frame.f_code.co_freevars[var_idx]
            elif byte_code in dis.hasname:
                arg = frame.f_code.co_names[arg_val]
            elif byte_code in dis.haslocal:
                arg = frame.f_code.co_varnames[arg_val]
            elif byte_code in dis.hasjrel:
                arg = frame.f_lasti + arg_val
            elif byte_code in dis.hasjabs:
                arg = arg_val
            else:
                arg = arg_val
            arguments = [arg]
        else:
            arguments = []

        return byte_name, arguments, offset

    def dispatch(self, instruction, argument):
        why = None
        try:  # 分支执行字节码对应的指令
            if instruction.startswith('UNARY_'):
                self.unaryOperator(instruction[6:])
            elif instruction.startswith('BINARY_'):
                self.binaryOperator(instruction[7:])
            elif instruction.startswith('INPLACE_'):
                self.inplaceOperator(instruction[8:])
            elif 'SLICE+' in instruction:
                self.sliceOperator(instruction)
            else:
                instruction_func = getattr(self, '' + str(instruction))
                if not instruction_func:
                    raise VirtualMachineError('unknown bytecode type: %s' % instruction)
                why = instruction_func(*argument)
        except:  # 错误处理
            self.last_exception = sys.exc_info()[:2] + (None,)
            why = 'exception'

        return why

    def resume_frame(self, frame):
        frame.f_back = self.frame
        val = self.run_frame(frame)
        frame.f_back = None
        return val

    def manage_block_stack(self, why):
        assert why != 'yield'

        block = self.frame.block_stack[-1]
        if block.type == 'loop' and why == 'continue':
            self.jump(self.return_value)
            why = None
            return why

        self.pop_block()
        self.unwind_block(block)

        if block.type == 'loop' and why == 'break':
            why = None
            self.jump(block.handler)
            return why

        if why == 'exception' and block.type in ['setup-except', 'finally']:
            self.push_block('except-handler')
            exctype, value, tb = self.last_exception
            self.push(tb, value, exctype)
            self.push(tb, value, exctype)
            why = None
            self.jump(block.handler)
            return why

        elif block.type == 'finally':
            if why in ('return', 'continue'):
                self.push(self.return_value)
            self.push(why)

            why = None
            self.push(block.handler)
            return why

        return why

    def push(self, *vals):
        self.frame.stack.extend(vals)

    def pop(self, i=0):
        return self.frame.stack.pop(-1 - i)

    def top(self):
        return self.frame.stack[-1]

    def peek(self, n):
        return self.frame.stack[-n]

    def jump(self, jump):
        self.frame.f_lasti = jump

    def popn(self, n):
        if n:
            ret = self.frame.stack[-n:]
            self.frame.stack[-n:] = []
            return ret
        else:
            return []

    def push_frame(self, frame):
        self.frames.append(frame)
        self.frame = frame

    def pop_frame(self):
        self.frames.pop()
        if self.frames:
            self.frame = self.frames[-1]
        else:
            self.frame = None

    def push_block(self, type, handler=None, level=None):
        if level is None:
            level = len(self.frame.stack)
        self.frame.block_stack.append(Block(type, handler, level))

    def pop_block(self):
        return self.frame.block_stack.pop()

    def unwind_block(self, block):
        if block.type == 'except-handler':
            offset = 3
        else:
            offset = 0

        while len(self.frame.stack) > block.level + offset:
            self.pop()

        if block.type == 'except-handler':
            tb, value, exctype = self.popn(3)
            self.last_exception = exctype, value, tb

    def POP_TOP(self):
        self.pop()

    def ROT_TWO(self):
        a, b = self.popn(2)
        self.push(b, a)

    def ROT_THREE(self):
        a, b, c = self.popn(3)
        self.push(c, a, b)

    def DUP_TOP(self):
        self.push(self.top())

    def DUP_TOP_TWO(self):
        a, b = self.popn(2)
        self.push(a, b, a, b)

    UNARY_OPERATORS = {
        'POSITIVE': operator.pos,
        'NEGATIVE': operator.neg,
        'NOT': operator.not_,
        'CONVERT': repr,
        'INVERT': operator.invert,
    }

    def unaryOperator(self, op):
        x = self.pop()
        self.push(self.UNARY_OPERATORS[op](x))

    def GET_ITER(self):
        x = self.pop()
        self.push(iter(x))

    def GET_YIELD_FROM_ITER(self):
        # TODO it is to be implemented after others
        pass

    BINARY_OPERATORS = {
        # TODO MATRIX_MULTIPLY is to be finished
        'POWER': pow,
        'MULTIPLY': operator.mul,
        'DIVIDE': getattr(operator, 'div', lambda x, y: None),
        'FLOOR_DIVIDE': operator.floordiv,
        'TRUE_DIVIDE': operator.truediv,
        'MODULO': operator.mod,
        'ADD': operator.add,
        'SUBTRACT': operator.sub,
        'SUBSCR': operator.getitem,
        'LSHIFT': operator.lshift,
        'RSHIFT': operator.rshift,
        'AND': operator.and_,
        'XOR': operator.not_,
        'OR': operator.or_,
    }

    def binaryOperator(self, op):
        x, y = self.popn(2)
        self.push(self.BINARY_OPERATORS[op](x, y))

    def inplaceOperator(self, op):
        x, y = self.popn(2)
        if op == 'POWER':
            y = x ** y
        elif op == 'MULTIPLY':
            y = x ** y
        elif op == 'FLOOR_DIVIDE':
            y = x // y
        elif op == 'TRUE_DIVIDE':
            y = x / y
        elif op == 'MODULO':
            y = x % y
        elif op == 'ADD':
            y = x + y
        elif op == 'SUBTRACT':
            y = x - y
        elif op == 'LSHIFT':
            y = x << y
        elif op == 'RSHIFT':
            y = x >> y
        elif op == 'AND':
            y = x & y
        elif op == 'XOR':
            y = x ^ y
        elif op == 'OR':
            y = x | y
        else:
            raise VirtualMachineError('Unknown in-place operator %s' % op)
        self.push(y)

    def sliceOperator(self, op):
        start = 0
        end = None
        op, count = op[:-2], int(op[-1])
        if count == 1:
            start = self.pop()
        elif count == 2:
            end = self.pop()
        elif count == 3:
            end = self.pop()
            start = self.pop()

        l = self.pop()
        if end is None:
            end = len(l)
        if op.startswith('STORE_'):
            l[start:end] = self.pop()
        elif op.startswith('DELETE_'):
            del l[start:end]
        else:
            self.push(l[start:end])

    def STORE_SUBSCR(self):
        x, y, z = self.popn(3)
        y[z] = x

    def DELETE_SUBSCR(self):
        x, y = self.popn(2)
        del x[y]

    def PRINT_EXPR(self):
        x = self.pop()
        print(x)

    def BREAK_LOOP(self):
        return 'break'

    def CONTINUE_LOOP(self, target):
        self.return_value = target
        return 'continue'

    def SET_ADD(self, i):
        val = self.pop()
        _set = self.peek(i)
        set.add(_set, val)

    def LIST_APPEND(self, i):
        val = self.pop()
        _list = self.peek(i)
        list.append(_list, val)

    def MAP_ADD(self, i):
        val, key = self.popn(2)
        _map = self.peek(i)
        dict.__setitem__(_map, key, val)

    def RETURN_VALUE(self):
        self.return_value = self.pop()
        if self.frame.generator:
            self.frame.generator.finished = True
        return 'return'

    def YIELD_VALUE(self):
        self.return_value = self.pop()
        return 'yield'

    def YIELD_FROM(self):
        # TODO after learning generator
        x = self.pop()
        pass

    def IMPORT_STAR(self):
        mod = self.pop()
        for attr in dir(mod):
            if attr[0] != '_':
                self.frame.f_locals[attr] = getattr(mod, attr)

    def POP_BLOCK(self):
        self.pop_block()

    def POP_EXCEPT(self):
        block = self.pop_block()
        if block.type != 'except-handler':
            raise Exception('popped block is not an except handler')
        self.unwind_block(block)

    def END_FINALLY(self):
        x = self.pop()
        if isinstance(x, str):
            why = x
            if why in ('return', 'continue'):
                self.return_value = self.pop()
            if why == 'silenced':
                block = self.pop_block()
                assert block.type == 'except-handler'
                self.unwind_block(block)
                why = None
        elif x is None:
            why = None
        elif issubclass(x, BaseException):
            exctype = x
            val = self.pop()
            tb = self.pop()
            self.last_exception = (exctype, val, tb)
            why = 'reraise'
        else:
            raise VirtualMachineError("Confused END_FINALLY")

        return why

    def SETUP_WITH(self, dest):
        ctxmgr = self.pop()
        self.push(ctxmgr.__exit__)
        ctxmgr_obj = ctxmgr.__enter__()
        self.push('finally', dest)
        self.push(ctxmgr_obj)

    # def WITH_CLEANUP_START(self):
    #     pass
    #
    # def WITH_CLEANUP_FINISH(self):
    #     pass

    def STORE_NAME(self, namei):
        name = self.pop()
        self.frame.f_locals[namei] = name

    def DELETE_NAME(self, namei):
        del self.frame.f_locals[namei]

    def UNPACK_SEQUENCE(self, count):
        seq = self.pop()
        for x in reversed(seq):
            self.push(x)

    def UNPACK_EX(self, counts):
        # TODO
        pass

    def STORE_ATTR(self, name):
        x, y = self.popn(2)
        setattr(y, name, x)

    def DELETE_ATTR(self, name):
        x = self.pop()
        delattr(x, name)

    def STORE_GLOBAL(self, namei):
        name = self.pop()
        self.frame.f_globals[namei] = name

    def DELETE_GLOBAL(self, namei):
        del self.frame.f_globals[namei]

    def LOAD_CONST(self, const):
        # TODO there exits some question: push co_consts[consti]
        self.push(const)

    def LOAD_NAME(self, name):
        if name in self.frame.f_locals:
            val = self.frame.f_locals[name]
        elif name in self.frame.f_globals:
            val = self.frame.f_globals[name]
        elif name in self.frame.f_builtins:
            val = self.frame.f_builtins[name]
        else:
            raise NameError("name '%s' is not defined" % name)
        self.push(val)

    def BUILD_TUPLE(self, count):
        _tuple = self.popn(count)
        self.push(tuple(_tuple))

    def BUILD_LIST(self, count):
        _list = self.popn(count)
        self.push(list(_list))

    def BUILD_SET(self, count):
        _set = self.popn(count)
        self.push(set(_set))

    def BUILD_MAP(self, count):
        # TODO it has been changed after Python 3.5
        l = self.popn(2 * count)
        d = {}
        for i in range(0, len(l) - 2, 2):
            d[l[i]] = l[i + 1]
        self.push(d)

    def BUILD_CONST_KEY_MAP(self, count):
        pass

    def BUILD_STRING(self, count):
        strings = self.popn(count)
        new_str = ''
        for string in strings:
            new_str += string
        self.push(new_str)

    def BUILD_TUPLE_UNPACK(self, count):
        # TODO
        pass

    def LOAD_ATTR(self, namei):
        x = self.pop()
        self.push(getattr(x, namei))

    COMPARE_OPERATORS = [
        operator.lt,
        operator.le,
        operator.eq,
        operator.ne,
        operator.gt,
        operator.ge,
        lambda x, y: x in y,
        lambda x, y: x not in y,
        lambda x, y: x is y,
        lambda x, y: x is not y,
        lambda x, y: issubclass(x, Exception) and issubclass(x, y),
    ]

    def COMPARE_OP(self, opnum):
        x, y = self.popn(2)
        self.push(self.COMPARE_OPERATORS[opnum](x, y))

    def IMPORT_NAME(self, name):
        level, fromlist = self.popn(2)
        self.push(
            __import__(name, self.frame.f_globals, self.frame.f_locals, fromlist, level)
        )

    def IMPORT_FROM(self, name):
        mod = self.pop()
        self.push(getattr(mod, name))

    def JUMP_FORWARD(self, delta):
        self.jump(delta)

    def POP_JUMP_IF_TRUE(self, target):
        x = self.pop()
        if x is True:
            self.jump(target)

    def POP_JUMP_IF_FALSE(self, target):
        x = self.pop()
        if x is False:
            self.jump(target)

    def JUMP_IF_TRUE_OR_POP(self, target):
        x = self.top()
        if x is True:
            self.jump(target)
        else:
            self.pop()

    def JUMP_IF_FALSE_OR_POP(self, target):
        x = self.top()
        if x is False:
            self.jump(target)
        else:
            self.pop()

    def JUMP_ABSOLUTE(self, target):
        self.jump(target)

    def FOR_ITER(self, delta):
        # TODO hasNext right or not ?
        x = self.top()
        try:
            v = next(x)
            self.push(v)
        except StopIteration:
            self.pop()
            self.jump(delta)

    def LOAD_GLOBAL(self, name):
        if name in self.frame.f_globals:
            val = self.frame.f_globals[name]
        elif name in self.frame.f_builtins:
            val = self.frame.f_builtins[name]
        else:
            raise NameError("global name '%s' is not defined" % name)
        self.push(val)

    def LOAD_DEREF(self, name):
        self.push(self.frame.cells[name].get())

    def STORE_DEREF(self, name):
        self.frame.cells[name].set(self.pop())

    def LOAD_LOCALS(self):
        self.push(self.frame.f_locals)

    def SETUP_LOOP(self, delta):
        self.push_block('loop', delta)

    def SETUP_EXCEPT(self, delta):
        self.push_block('setup-except', delta)

    def SETUP_FINALLY(self, delta):
        self.push_block('finally', delta)

    def LOAD_FAST(self, name):
        if name in self.frame.f_locals:
            val = self.frame.f_locals[name]
        else:
            raise UnboundLocalError("local variable '%s' referenced before assignment" % name)
        self.push(val)

    def STORE_FAST(self, name):
        self.frame.f_locals[name] = self.pop()

    def DELETE_FAST(self, name):
        del self.frame.f_locals[name]

    def LOAD_CLOSURE(self, i):
        self.push(self.frame.cells[i])

    def MAKE_CLOSURE(self, argc):
        name = self.pop()
        closure, code = self.popn(2)
        defaults = self.popn(argc)
        globs = self.frame.f_globals
        func = Function(name, code, globs, defaults, closure, self)
        self.push(func)

    def CALL_FUNCTION(self, argc):
        return self.call_function(argc, [], {})

    def CALL_FUNCTION_VAR(self, argc):
        args = self.pop()
        return self.call_function(argc, args, {})

    def CALL_FUNCTION_KW(self, argc):
        kwargs = self.pop()
        return self.call_function(argc, [], kwargs)

    def CALL_FUNCTION_VAR_KW(self, argc):
        args, kwargs = self.popn(2)
        return self.call_function(argc, args, kwargs)

    # def CALL_FUNCTION_EX(self, flags):
    #     args, kwargs = self.popn(2)
    #     return self.call_function(argc, args, kwargs)

    def LOAD_METHOD(self, namei):
        pass

    def CALL_METHOD(self, argc):
        pass

    def MAKE_FUNCTION(self, flags):
        name = self.pop()
        code = self.pop()
        defaults = self.popn(flags)
        globs = self.frame.f_globals
        func = Function(name, code, globs, defaults, None, self)
        self.push(func)

    def call_function(self, argc, args, kwargs):
        len_kw, len_pos = divmod(argc, 256)
        named_args = {}
        for i in range(len_kw):
            key, val = self.popn(2)
            named_args[key] = val
        named_args.update(kwargs)
        pos_args = self.popn(len_pos)
        pos_args.extend(args)

        func = self.pop()
        frame = self.frame
        if hasattr(func, 'im_func'):
            if func.__self__:
                pos_args.insert(0, func.__self__)
            if not isinstance(pos_args[0], func.__self__.__class__):
                raise TypeError(
                    'unbound method %s() must be called with %s instance '
                    'as first argument (got %s instance instead)' % (
                        func.__func__.__name__,
                        func.__self__.__class__.__name__,
                        type(pos_args[0]).__name__,
                    )
                )
            func = func.__func__
        retval = func(*pos_args, **named_args)
        self.push(retval)

    def BUILD_SLICE(self, count):
        if count == 2:
            x, y = self.popn(2)
            self.push(slice(x, y))
        elif count == 3:
            x, y, z = self.popn(3)
            self.push(slice(x, y, z))
        else:
            raise VirtualMachineError("Strange BUILD_SLICE count: %r" % count)

    def LOAD_BUILD_CLASS(self):
        self.push(builtins.__build_class__)

    def STORE_LOCALS(self):
        self.frame.f_locals = self.pop()

    def EXTENDED_ARG(self, ext):
        pass

    def FORMAT_VALUE(self, flags):
        # TODO py3.6
        pass


if __name__ == '__main__':
    with open('Frame.py', 'r') as f:
        content = f.read()
    code_obj = compile(content, 's', 'exec')
    print(code_obj.co_names)

