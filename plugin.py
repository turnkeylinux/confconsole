#!/usr/bin/python
import re
import os
import sys
import imp
import importlib.util
import importlib
from traceback import format_exc
from collections import OrderedDict

from types import ModuleType
from typing import Callable, Any, Union, Optional, Iterable
#from typing_extensions import TypeAlias
import typing


class PluginError(Exception):
    pass


class EventError(Exception):
    pass


class ModuleInterface(ModuleType):
    # this is a hack, we pretend all plugin modules are derived of this
    module_name: str

    def run(self) -> Optional[str]:
        ...

    def doOnce(self) -> None:
        ...

class EventManager(object):
    _handlers: dict[str, list[Callable[[], None]]]
    _events: set[str]

    ''' Object to handle event/handler interaction '''
    def __init__(self) -> None:
        self._handlers = {}
        self._events = set()

    def add_event(self, event: str) -> Callable[[], None]:
        ''' Adds event and returns callback function to `fire` event '''
        self._events.add(event)
        if event not in self._handlers:
            self._handlers[event] = []

        def fire() -> None:
            self.fire_event(event)

        fire.__doc__ = ' Function to fire the `%s` event ' % event
        return fire

    def add_handler(self, event: str, handler: Callable[[], None]) -> None:
        ''' Adds a handler to an event '''
        if event not in self._handlers:
            self._events.add(event)
            self._handlers[event] = []
        self._handlers[event].append(handler)

    def fire_event(self, event: str) -> None:
        ''' Fire event, calling all handlers in order '''
        if event not in self._events:
            return  # if event hasn't been registered, don't attempt to fire it

        if event not in self._handlers:
            return  # if event has no handlers, don't attempt to fire it

        for handler in self._handlers[event]:
            try:
                handler()  # handler passed no arguments; can change if needed
            except:
                sys.stderr.write('An Exception has occured within an event'
                                 ' handler whilst attempting to handle event'
                                 ' "%s"\n%s' % (event, format_exc()))


class Plugin(object):
    ''' Object that holds various information about a `plugin` '''

    parent: Optional[str]
    
    def __init__(self, path: str, module_globals: dict[str, Any]) -> None:
        self.path = path
        # for weighted ordering
        self.real_name = os.path.basename(path)
        # for menu entry
        self.name = re.sub(r'^[\d]*', '', self.real_name).replace('_', ' ')

        self.parent = None

        # used for imp.find_module
        self.module_name = os.path.splitext(self.real_name)[0]

        spec = importlib.util.spec_from_file_location(self.module_name, self.path)
        assert spec is not None
        assert spec.loader is not None
        self.module = typing.cast(ModuleInterface,
                importlib.util.module_from_spec(spec))
        


        for k in module_globals:
            setattr(self.module, k, module_globals[k])
        setattr(self.module, 'PLUGIN_PATH', self.path)

        assert isinstance(spec.loader, importlib.abc.Loader)
        spec.loader.exec_module(self.module)

        # after module is found, it's safe to use pretty name
        self.module_name = os.path.splitext(self.name)[0]

    def updateGlobals(self, newglobals: dict[str, Any]) -> None:
        for k in newglobals:
            setattr(self.module, k, newglobals[k])

    def run(self) -> Optional[str]:
        assert hasattr(self.module, 'run')
        ret: Optional[str] = self.module.run()
        assert ret is None or isinstance(ret, str)

        # default behaviour is to go to previous
        # menu after exiting if not otherwise specified
        if hasattr(self, 'parent'):
            return ret or self.parent
        else:
            return ret or 'advanced'


class PluginDir(object):
    '''Object that mimics behaviour of a plugin but acts only as a menu node'''

    parent: Optional[str]
    plugins: list[Union[Plugin, 'PluginDir']]

    def __init__(self, path: str, module_globals: dict[str, Any]):
        self.path = path
        self.real_name = os.path.basename(path)
        self.name = re.sub('^[\d]*', '', self.real_name).replace('_', ' ')

        self.parent = None

        self.module_name = self.name

        self.module_globals = module_globals

        if os.path.isfile(os.path.join(path, 'description')):
            with open(os.path.join(path, 'description'), 'r') as fob:
                self.description = fob.read()
        else:
            self.description = ''

    def updateGlobals(self, newglobals: dict[str, Any]) -> None:
        self.module_globals.update(newglobals)

    def run(self) -> Optional[str]:
        items = []
        plugin_map: dict[str, Union[Plugin, PluginDir]] = {}
        for plugin in self.plugins:
            if isinstance(plugin, Plugin) and hasattr(plugin.module, 'run'):
                items.append((plugin.module_name.capitalize(),
                              str(plugin.module.__doc__)))
                plugin_map[plugin.module_name.capitalize()] = plugin
            elif isinstance(plugin, PluginDir):
                items.append((plugin.module_name.capitalize(),
                              plugin.description))
                plugin_map[plugin.module_name.capitalize()] = plugin

        retcode, choice = self.module_globals['console'].menu(
                self.module_name.capitalize(),
                self.module_name.capitalize()+'\n', items, no_cancel=False)

        if retcode != 'ok':
            if not self.parent:
                return 'advanced'
            else:
                return self.parent

        if choice in plugin_map:
            return plugin_map[choice].path
        else:
            v: str = '_adv_' + choice.lower()
            return v


class PluginManager(object):
    ''' Object that holds various information about multiple `plugins` '''

    path_map: OrderedDict[str, Union[Plugin, PluginDir]]  = OrderedDict()

    def __init__(self, path: str, module_globals: dict[str, Any]) -> None:
        path = os.path.realpath(path)  # Just in case
        path_map: dict[str, Union[Plugin, PluginDir]] = {}

        module_globals.update({
            'impByName': lambda *a, **k: self.impByName(*a, **k),
            'impByDir': lambda *a, **k: self.impByDir(*a, **k),
            'impByPath': lambda *a, **k: self.impByPath(*a, **k),
        })

        self.module_globals = module_globals

        if not os.path.isdir(path):
            raise PluginError('Plugin directory "{}" does not exist!'
                              ''.format(path))

        for root, dirs, files in os.walk(path):
            for file_name in files:
                if not file_name.endswith('.py'):
                    continue

                file_path = os.path.join(root, file_name)
                if os.path.isfile(file_path):
                    if not os.stat(file_path).st_mode & 0o111 == 0:
                        path_map[file_path] = Plugin(file_path, module_globals)

            for dir_name in dirs:
                if dir_name == '__pycache__':
                    continue
                dir_path = os.path.join(root, dir_name)

                if os.path.isdir(dir_path):
                    path_map[dir_path] = PluginDir(dir_path, module_globals)

        for key in path_map:
            plugin = path_map[key]
            if isinstance(plugin, Plugin) and hasattr(plugin.module, 'doOnce'):
                # Run plugin init
                plugin.module.doOnce()
        self.path_map = OrderedDict(sorted(path_map.items(),
                                           key=lambda x: x[0]))

        for key in self.path_map:
            if os.path.isdir(key):
                sub_plugins = self.getByDir(key)
                for plugin in sub_plugins:
                    plugin.parent = key
                v = self.path_map[key]
                assert isinstance(v, PluginDir)
                v.plugins = list(sub_plugins)

    def updateGlobals(self, newglobals: dict[str, Any]) -> None:
        for path, plugin in self.path_map.items():
            plugin.updateGlobals(newglobals)
            # self.module_globals.update(newglobals)

    def getByName(self, name: str) -> Iterable[Union[Plugin, PluginDir]]:
        ''' Return list of plugin objects matching given name '''
        return filter(lambda x: x.module_name == name, self.path_map.values())

    def getByDir(self, path: str) -> Iterable[Union[Plugin, PluginDir]]:
        ''' Return a list of plugin objects in given directory '''
        plugins = []
        for path_key in self.path_map:
            if os.path.dirname(path_key) == path:
                plugins.append(self.path_map[path_key])
        return plugins

    def getByPath(self, path: str) -> Optional[Union[Plugin, PluginDir]]:
        ''' Return plugin object with exact given path or None'''
        return self.path_map.get(path, None)

    # -- Used by plugins
    def impByName(self, name: str) -> Iterable[ModuleInterface]:
        '''Return a list of python modules (from plugins excluding PluginDirs)
        matching given name'''

        modules = [ x.module for x in
                self.getByName(name) if isinstance(x, Plugin) ]

        return filter(None, modules)

    def impByDir(self, path: str) -> Iterable[ModuleInterface]:
        '''Return a list of python modules (from plugins excluding PluginDirs)
        in given directory'''

        modules = [ x.module for x in
                self.getByDir(path) if isinstance(x, Plugin) ]

        return filter(None, modules)

    def impByPath(self, path: str) -> Optional[ModuleInterface]:
        ''' Return a python module from plugin at given path or None '''
        out = self.getByPath(path)
        if out and isinstance(out, Plugin):
            return out.module
        return None

# em = EventManager()
# pm = PluginManager('plugins.d', {'eventManager': em})

# for plugin in pm.plugins:
#     print '\nRunning:', plugin.path, '\n','-'*10
#     plugin.module.run()
