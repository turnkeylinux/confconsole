#!/usr/bin/python
import re
import os
import sys
import imp
from traceback import format_exc
from collections import OrderedDict

class PluginError(Exception):
    pass

class EventError(Exception):
    pass

class EventManager(object):
    ''' Object to handle event/handler interaction '''
    def __init__(self):
        self._handlers = {}
        self._events = set()

    def add_event(self, event):
        ''' Adds event and returns callback function to `fire` event '''
        self._events.add(event)
        if not self._handlers.has_key(event):
            self._handlers[event] = []

        def fire():
            self.fire_event(event)

        fire.__doc__ = ' Function to fire the `%s` event ' % event
        return fire

    def add_handler(self, event, handler):
        ''' Adds a handler to an event '''
        if not self._handlers.has_key(event):
            self._events.add(event)
            self._handlers[event] = []
        self._handlers[event].append(handler)

    def fire_event(self, event):
        ''' Fire event, calling all handlers in order '''
        if not event in self._events:
            return # if the event hasn't been registered, don't attempt to fire it

        if not self._handlers.has_key(event):
            return # if the event has no handlers, don't attempt to fire it

        for handler in self._handlers[event]:
            try:
                handler() # handler is passed no arguments, this could be changed if needed
            except:
                sys.stderr.write('An Exception has occured within an event handler whilst attempting to handle event "%s"\n%s' % (event, format_exc()))
                
                

class Plugin(object):
    ''' Object that holds various information about a `plugin` '''

    def __init__(self, path, module_globals):
        self.path = path
        self.real_name = os.path.basename(path) # for weighted ordering
        self.name = re.sub('^[\d]*', '', self.real_name).replace('_', ' ') # for menu entry

        # used for imp.find_module
        self.module_name = os.path.splitext(self.real_name)[0]

        # find the module
        module_fob, module_pathname, module_description = imp.find_module(self.module_name, [os.path.dirname(self.path)])

        try:
            self.module = imp.load_module(self.module_name, module_fob, module_pathname, module_description)
        finally:
            module_fob.close()

        for k in module_globals:
            setattr(self.module, k, module_globals[k])

    def run(self):
        ret = self.module.run()
        # default behaviour is to go to previous
        # menu after exiting if not otherwise specified
        if hasattr(self, 'parent'):
            return ret or self.parent
        else:
            return ret or 'advanced'

class PluginDir(object):
    ''' Object that mimics behaviour of a plugin but acts only as a menu node '''

    def __init__(self, path, module_globals):
        self.path = path
        self.real_name = os.path.basename(path)
        self.name = re.sub('^[\d]*', '', self.real_name).replace('_', ' ')

        self.module_name = self.name

        self.module_globals = module_globals

        if os.path.isfile(os.path.join(path, 'description')):
            with open(os.path.join(path, 'description'), 'r') as fob:
                self.description = fob.read()
        else:
            self.description = ''


    def run(self):
        items = []
        plugin_map = {}
        for plugin in PluginManager.getByDir(self.path):
            if isinstance(plugin, Plugin) and hasattr(plugin.module, 'run'):
                items.append((plugin.module_name.capitalize(), str(plugin.module.__doc__)))
                plugin_map[plugin.module_name.capitalize()] = plugin
            elif isinstance(plugin, PluginDir):
                items.append((plugin.module_name.capitalize(), plugin.description))
                plugin_map[plugin.module_name.capitalize()] = plugin

        items.append(('Back', ''))

        retcode, choice = self.module_globals['console'].menu(self.module_name.capitalize(), self.module_name.capitalize()+'\n', items, no_cancel = False)

        if retcode is not 0: # confconsole.TurnkeyConsole.OK
            return 'usage'

        if choice == 'Back':
            if not hasattr(self, 'parent'):
                return 'advanced'
            else:
                return self.parent

        if choice in plugin_map:
            return plugin_map[choice].path
        else:
            return '_adv_' + choice.lower()

class PluginManager(object):
    ''' Object that holds various information about multiple `plugins` '''

    path_map = OrderedDict()

    def __init__(self, path, module_globals):
        path = os.path.realpath(path) # Just in case
        path_map = {}

        module_globals.update({
            'impByName': PluginManager.getByName,
            'impByDir': PluginManager.getByDir,
            'impByPath': PluginManager.getByPath,
        })

        if not os.path.isdir(path):
            raise PluginError('Plugin directory "{}" does not exist!'.format(path))

        for root, dirs, files in os.walk(path):
            for file_name in files:
                if not file_name.endswith('.py'):
                    continue

                file_path = os.path.join(root, file_name)
                if os.path.isfile(file_path):
                    if not os.stat(file_path).st_mode & 0111 == 0:
                        current_plugin = Plugin(file_path, module_globals)
                        path_map[file_path] = current_plugin

            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                
                if os.path.isdir(dir_path):
                    current_plugin = PluginDir(dir_path, module_globals)
                    path_map[dir_path] = current_plugin

        for key in self.path_map:
            plugin = self.path_map[key]
            if isinstance(plugin, Plugin) and hasattr(plugin.module, 'doOnce'):
                # Run plugin init
                plugin.module.doOnce()
        PluginManager.path_map = OrderedDict(sorted(path_map.items(), key = lambda x: x[0]))
 
    @staticmethod
    def getByName(name):
        ''' Return list of plugin objects matching given name '''
        return filter(lambda x:x.module_name == name, PluginManager.path_map.values())

    @staticmethod
    def getByDir(path):
        ''' Return a list of plugin objects in given directory '''
        plugins = []
        for path_key in PluginManager.path_map:
            if os.path.dirname(path_key) == path:
                plugins.append(PluginManager.path_map[path_key])
        return plugins

    @staticmethod
    def getByPath(path):
        ''' Return plugin object with exact given path or None'''
        return PluginManager.path_map.get(path)

    #-- Used by plugins
    @staticmethod
    def impByName(name):
        ''' Return a list of python modules (from plugins excluding PluginDirs) matching given name '''
        return filter(map(lambda x:x.module if hasattr(x, 'module') else None, PluginManager.getByName(name)))

    @staticmethod
    def impByDir(path):
        ''' Return a list of python modules (from plugins excluding PluginDirs) in given directory '''
        return filter(map(lambda x:x.module if hasattr(x, 'module') else None, PluginManager.getByDir(path)))

    @staticmethod
    def impByPath(path):
        ''' Return a python module from plugin at given path or None '''
        return PluginManager.getByPath(path).module

#em = EventManager()
#pm = PluginManager('plugins.d', {'eventManager': em})

#for plugin in pm.plugins:
#    print '\nRunning:', plugin.path, '\n','-'*10
#    plugin.module.run()
