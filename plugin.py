#!/usr/bin/python
import re
import os
import sys
import imp
from traceback import format_exc


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

    def __init__(self, path, module_globals = {}):
        self.path = path
        self.real_name = os.path.basename(path) # for weighted ordering
        self.name = re.sub('^[\d]*', '', self.real_name) # for menu entry

        # used for imp.find_module
        self.module_name = self.real_name.rstrip('.py')

        # find the module
        module_fob, module_pathname, module_description = imp.find_module(self.module_name, [os.path.dirname(self.path)])

        try:
            self.module = imp.load_module(self.module_name, module_fob, module_pathname, module_description)
        finally:
            module_fob.close()

        # set given globals, dialog and event_manager for example
        for name in module_globals:
            val = module_globals[name]
            setattr(self.module, name, val)

    def run(self):
        return self.module.run()

class PluginDir(object):
    ''' Object that mimics behaviour of a plugin but acts only as a menu node '''

    def __init__(self, path, module_globals = {}):
        self.path = path
        self.real_name = os.path.basename(path)
        self.name = re.sub('^[\d]*', '', self.real_name)

        self.module_name = self.name
        self.module_globals = module_globals
        self.plugins = []

        assert 'console' in self.module_globals, 'console not passed to PluginDir in module_globals'

    def run(self):
        pass

class PluginManager(object):
    ''' Object that holds various information about multiple `plugins` '''

    def __init__(self, path, plugin_globals = {}):
        self.plugins = []
        self.names = set()

        self.path_map = {}

        if not os.path.isdir(path):
            raise PluginError('Plugin directory "{}" does not exist!'.format(path))

        for root, dirs, files in os.walk(path):
            print 'once'
            for file_name in files:
                file_path = os.path.join(root, file_name)
                print file_name
                if os.path.isfile(file_path):
                    if not os.stat(file_path).st_mode & 0111 == 0:
                        current_plugin = Plugin(file_path, plugin_globals)
                        self.path_map[file_path] = current_plugin

                        for plugin in self.plugins:
                            print 'a'
                            if root == plugin.path:
                                plugin.plugins.append(current_plugin)
                            else:
                                self.plugins.append(current_plugin)

            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                
                if os.path.isdir(dir_path):
                    current_plugin = PluginDir(file_path, plugin_globals)
                    self.path_map[dir_path] = current_plugin

                    self.plugins.append(current_plugin)

        # This should sort paths correctly
        self.plugins = sorted(self.plugins, key=lambda x:x.path.lstrip(path).split('/'))

        for plugin in self.plugins:
            if isinstance(plugin, Plugin) and hasattr(plugin.module, 'doOnce'):
                plugin.module.doOnce()

        print self.path_map
        exit(1)

    def getByName(self, name):
        return filter(lambda x:x.module_name == name, self.plugins)

#em = EventManager()
#pm = PluginManager('plugins.d', {'eventManager': em})

#for plugin in pm.plugins:
#    print '\nRunning:', plugin.path, '\n','-'*10
#    plugin.module.run()
