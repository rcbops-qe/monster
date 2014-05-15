import inspect


def module_classes(module):
    return {k.lower(): v for (k, v) in
            inspect.getmembers(module, inspect.isclass)}
