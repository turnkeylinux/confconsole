''' I will be the description '''
#
'''
Note: plugins must be executable


Global Variables:

eventManager - allows access to the event system
    eventManager.add_event(<name>) adds an event of said name
    eventManager.add_handler(<name>, <func>) adds handler to event
    eventManager.fire_event(<name>) call all handers for said event
console - allows python dialog access (see confconsole.py)

impByName   - a function, takes a name and returns all plugin modules matching that name.
impByDir    - a function, takes a path and returns all plugin modules within that directory.
impByPath   - a function, takes a path and returns the plugin module at specified path or None.


Plugin Functions/Scope:

main body - the main body is run at load time of the plugin, none of the global variables are
            set at this point, neither are all the plugins loaded.

doOnce() - if defined is run once, after loading all plugins and before running confconsole.

run() - if defined is run whenever the plugin is selected, if not defined, no menu entry is
        created for this plugin.
'''


def doOnce():
    eventManager.add_event('test_event')


def run():
    eventManager.fire_event('test_event')
