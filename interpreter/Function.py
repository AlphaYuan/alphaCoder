import inspect
import types


def make_cell(val):
    func = (lambda x: lambda: x)(val)
    return func.func_closure[0]


class Function(object):
    __slots__ = [
        'func_code', 'func_name', 'func_defaults', 'func_globals', 'func_locals',
        'func_closure', 'func_dict', 'func_closure', '__name__', '__dict__',
        '__doc__', 'vm', 'func',
    ]

    def __init__(self, name, code, globs, defaults, closure, vm):
        self.vm = vm
        self.func_code = code
        self.func_name = self.__name__ = name or code.co_name
        self.func_globals = globs
        self.func_locals = self.vm.frame.f_locals
        self.func_defaults = tuple(defaults)
        self.func_closure = closure
        self.__dict__ = {}
        self.__doc__ = code.co_consts[0] if code.co_consts else None

        kw = {'argdefs': self.func_defaults}

        if closure:
            kw['closure'] = tuple(make_cell(0) for _ in closure)

        self.func = types.FunctionType(code, globs, **kw)

    def __repr__(self):
        return '<Function %s at 0x%016x>' % (self.__name__, id(self))

    def __get__(self, instance, owner):
        if instance is not None:
            return Method(instance, owner, self)
        return self

    def __call__(self, *args, **kwargs):
        # print('function __call__')
        callargs = inspect.getcallargs(self.func, *args, **kwargs)

        frame = self.vm.make_frame(self.func_code, callargs, self.func_globals, {})

        CO_GENERATOR = 32
        if self.func_code.co_flags & CO_GENERATOR:
            gen = Generator(frame, self.vm)
            frame.generator = gen
            ret = gen
        else:
            ret = self.vm.run_frame(frame)

        return ret


class Method(object):

    def __init__(self, obj, _class, func):
        self.__self__ = obj
        self.__self__.__class__ = _class
        self.__func__ = func

    def __repr__(self):
        name = '%s.%s' % (self.__self__.__class__.__name__, self.__func__.__name__)
        if self.__self__ is not None:
            return '<Bound Method %s of %s>' % (name, self.__self__)
        else:
            return '<Unbound Method %s>' % (name,)

    def __call__(self, *args, **kwargs):
        if self.__self__ is not None:
            return self.__func__(self.__self__, *args, **kwargs)
        else:
            return self.__func__(*args, **kwargs)


class Generator(object):

    def __init__(self, g_frame, vm):
        self.g_frame = g_frame
        self.vm = vm
        self.first = True
        self.finished = False

    def __iter__(self):
        return self

    def __next__(self):
        if not self.first:
            self.g_frame.stack.append(None)
        self.first = False

        val = self.vm.resume_frame(self.g_frame)
        if self.finished:
            raise StopIteration

        return val

    __next__ = next
