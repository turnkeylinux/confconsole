ConfConsole Plugins
===================

ConfConsole menu options can be easily added by way of plugins. 

Plugins are python source files which are placed within the ConfConsole 
directory. ConfConsole will load any applicable files and provide them 
to the user as menu options.


How are plugins loaded?
-----------------------

First a tree is generated from "plugins.d". Every directory is a menu or
sub-menu and every executable .py script is an entry of the parent 
directory's menu. Note ``plugins.d`` does not have a description as it is
not chosen from a menu.

For each plugin in the tree, the main body (top level) of the plugin is
run. Because of this you should not put anything but setup related code
here {where?} and you definitely should not rely on other plugins already 
being setup. Note that additional variables and functions avaliable to 
plugins are NOT avaliable at this point.

The plugin .py file(s) docstring provides the description for the menu-
entry in confconsole. To set a menu-entry description for a directory, 
place a text "description" file within the directory. 

Next, the ``doOnce`` function (optional) will be run once after every 
plugin is loaded. Note that while all plugins will be loaded, not all 
plugins will be ready at this point. However you do have the ability to 
work with them if you so choose. {what? how?}

Lastly the ``run`` function will be run whenever your plugin's menu entry
is clicked within confconsole. If the ``run`` function is not present in 
a plugin, then it's menu entry will not be created.


How do I interact with the user?
--------------------------------

The ``console`` variable is an instance of the ``Console`` object in 
confconsole.py. It is a simple interface using pythondialog-wrapper to 
allow basic console gui functionality. This, as with all other globals,
will be avaliable as soon as the ``doOnce`` function is run. Note that 
you should NEVER force any interaction until confconsole is fully started.
This could cause issues in headless builds for example which expect to 
be able to reach ``usage`` (first screen of confconsole) before any 
interaction.

The following methods are avaliable from ``console``:

- infobox(text)
    displays text on the screen, this is NOT blocking if you want
    the box to block momentarily use ``time.sleep(seconds)``
    afterwards. Otherwise this is usually used to display information
    during a long-running operation.

    returns 0.

    example: ``console.infobox("some text")``
    
- yesno(text)
    displays text on the screen with a yes/no prompt.
    returns 0 if yes, 1 if no.

    example: ``console.yesno("Are you sure?")``

- msgbox(title, text, button_label="ok")
    by default, displays text on the screen with a ok prompt. the ok can be
    changed to anything via button label.
    returns 0 

    example: ``console.msgbox("Warning", "You may need to restart for changes to take effect")``

- inputbox(title, text, init='', ok_label="OK", cancel_label="Cancel")
    displays text on the screen in title boxed with an input box
    (starting with the value ``init``) and a ok/cancel prompt which
    can be changed via the ``ok_label`` and ``cancel_label`` arguments.

    returns a tuple of (0 if ok or 1 if cancel, human_input)

    example: ``console.inputbox("Email", "Please enter you're email address", "user@example.com")``


- menu(title, text, choices, no_cancel=False)
    displays text on the screen in titled box along with a list of
    selectable options (choices), and optionally a cancel button.

    choices should be a list or tuple of length 2, each item of each
    tuple being a list of strings. The first collection of strings
    are the item names, the second are the item descriptions.

    returns a tuple of (0 if ok or 1 if cancel, option)

    example::
        console.menu("Favorite number", "choose a number",
            [
                [ '1', "dummy description for 1" ],
                [ '2', "dummy description for 2" ],
                [ '3', "dummy description for 3" ]
            ]
        )

- form(title, text, fields, ok_label="Apply", cancel_label="Cancel")
    displays text on the screen in title box along with a series of
    labeled input boxes and an apply/cancel prompt (button labels can
    be changed via label arguments)

    fields must be a collection of
        ``(label, item, field_length, input_length)``
    
    where ``label`` is a string that will display before the input
    box and ``item`` is the default text written in the field's
    input.

    field_length and input_length are integers that respectively
    specify the number of characters used for displaying the field and
    the maximum number of characters that can be entered for this
    field. These values also also determine writability of fields.

    if field_length is 0 it cannot be modified and it's contents
    determines size.

    if field_length is negative the field cannot be altered and the
    opposite of field_length determines it's size. {huh?}

    if input length is 0, it is set to field_length

    the return value is a tuple of (status, fields) where status
    is (0 if ok or 1 if cancel). And fields are the value inputted
    for each field in order.

Console is essentially just a wrapper for ``python dialog``. While not all 
methods are exposed and not all arguments to said methods are exposed, the 
documentation for python dialog largly still applies. 

http://pythondialog.sourceforge.net/doc/


How do I interact with other plugins?
-------------------------------------

For inter-plugin communication there are a few options, firstly there are
the ``imp*`` functions, which handle importing plugins. It's important that
you use this for plugins and not a normal ``import`` as the ``imp*`` 
function will return a version with it's additional globals set. A normal 
``import`` will load it as a normal python file.

The imp functions are as follows

- impByName
    does exactly as it implies, returns a list of all plugins matching given 
    name

- impByDir
    returns a list of all plugins within the given directory name (that is a
    sub-directory of plugins.d)

- impByPath
    returns a single plugin matching the exact relative path from plugins.d

In addition to these imp functions there is a shared eventManager between
all plugins which can also be used for cross-plugin communication. This 
event manager is exposed as the variable ``eventManager``

The event manager is rather simple. Events can be any hashable object,
although usually it makes more sense to use something obvious such as a 
string. Likewise, an event handler is any callable object but usually a 
function.

There are 3 functions exposed from the event manager

- add_event(name)
    this adds an event to the list of events owned by the event manager and returns
    a convenience function which will fire the event. Note that this convenience
    function is exactly that and is not necessary.

- add_handler(name, handler)
    this adds a handler for the corrosponding event. If the event does not exist it
    is created silently. This function returns None

- fire_event(name)
    this calls each handler in the order they were registered for the given event.


Other Information
-----------------

For an example of a minimum valid plugin, check plugins.d/example.py, to see it
in action just ``chmod +x plugins.d/example.py`` and run confconsole.

To see examples of other functionality, please see the source code of the other 
provided plugins.
