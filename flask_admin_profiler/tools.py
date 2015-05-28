import types
import inspect
import pprint


IGNORED_ATTRS = set(('__doc__', '__class__', '__hash__', '__new__', '__subclasshook__', '__all__', '__builtins__'))


# Repr handlers
repr_handlers = {}


def repr_handler(obj_type):
    def wrapper(fn):
        repr_handlers[obj_type] = fn
        return fn

    return wrapper


@repr_handler(dict)
def repr_dict(obj):
    return 'dict, len: %d, {%s}' % (len(obj),
                                    ', '.join('%s: %s' % (repr(k), repr(v)) for k, v in sorted(obj.items())))


@repr_handler(set)
def repr_set(obj):
    return 'set, len: %d, (%s)' % (len(obj), ', '.join('%s' % repr(v) for v in sorted(obj)))


def _format_str(obj):
    return '%s, len: %d, %s' % (type(obj).__name__, len(obj), obj)


@repr_handler(str)
def repr_str(obj):
    return _format_str(obj)


@repr_handler(unicode)
def repr_unicode(obj):
    return _format_str(obj)


def get_type(obj):
    return getattr(type(obj), '__name__', None)


def get_repr(obj, limit=None):
    type_name = getattr(type(obj), '__name__', None)
    handler = repr_handlers.get(type_name, repr)

    try:
        val = handler(obj)
    except Exception as ex:
        val = 'Failed to format object: %s' % ex

    if limit and len(val) > limit:
        val = val[:limit - 3] + '...'

    return val


# Pretty printing
pprint_handlers = {}


def handler(obj_type):
    def wrapper(fn):
        repr_handlers[obj_type] = fn
        return fn

    return wrapper


def pretty_print(obj):
    type_name = getattr(type(obj), '__name__', None)
    handler = pprint_handlers.get(type_name, None)

    if handler is not None:
        return handler(obj)

    if pprint.isrecursive(obj):
        return get_repr(obj)

    try:
        return pprint.pformat(obj)
    except:
        return get_repr(obj)


# Public attributes
def get_public_attrs(obj):
    attrs = []

    obj_type = type(obj)

    for name in dir(obj):
        if name in IGNORED_ATTRS:
            continue

        type_ref = getattr(obj_type, name, None)

        if type_ref is not None and isinstance(type_ref, property):
            continue

        val = getattr(obj, name)

        if inspect.ismethoddescriptor(type_ref):
            continue

        if isinstance(val, types.BuiltinFunctionType):
            continue

        if inspect.ismethod(val):
            continue

        attrs.append((name, get_repr(val)))

    return attrs
