import sys
import os
from setuptools import find_packages
from pkgutil import iter_modules
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent.parent
PACKAGE = 'correlation'
NAMESPACE = 'seeq.addons'


def _clear_cache(foo):
    """
    Clears the cache of only one function

    Parameters
    ----------
    foo: {obj},
        Function object whose cache will be clear

    Returns
    -------
    None
    """
    try:
        foo.cache_clear()
        print("Cache of function '{}' has been cleared".format(foo.__name__))
    except AttributeError:
        raise AttributeError('Function "{}" does not utilize cache. Nothing to clear'.format(foo.__name__))
    return


def clear_cache_all():
    """
    Inspects the seeq.addons.causality module and clears the cache of all objects

    """
    modules = find_all_modules(PACKAGE_DIR)
    package_foos = find_all_functions(modules, PACKAGE)
    for foo in package_foos:
        try:
            foo.cache_clear()
            print("Cache of function '{}' has been cleared".format(foo.__name__))
        except AttributeError:
            pass


def find_all_modules(package_dir):
    modules = set()
    packages = find_packages(package_dir)
    # noinspection PyProtectedMember
    for pkg in packages:
        # noinspection PyProtectedMember
        pkgpath = os.path.join(package_dir, os.path.normpath(pkg.replace('.', '/')))
        if sys.version_info.major == 2 or (sys.version_info.major == 3 and sys.version_info.minor < 6):
            for _, name, ispkg in iter_modules([pkgpath]):
                if not ispkg:
                    modules.add(pkg + '.' + name)
        else:
            for info in iter_modules([pkgpath]):
                if not info.ispkg:
                    modules.add(pkg + '.' + info.name)
    return modules


def find_all_functions(modules, package_name):
    all_foos = []

    for module in modules:
        imported = __import__('.'.join([NAMESPACE, module]), fromlist=[''])
        foos = [v for k, v in imported.__dict__.items() if callable(v)]
        all_foos.extend(foos)

    package_foos = [x for x in all_foos if package_name in x.__module__]
    return package_foos
