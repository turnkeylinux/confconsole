"""Actual Confconsole menu loop with an isolated shared-UI service fixture."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
# Exercise the image's real console, including its terminal sizing adapter.
# Only the candidate plugin directory and service-response fixture are selected.
sys.path.insert(0, '/usr/lib/confconsole')
import confconsole
confconsole.PLUGIN_PATH = str(ROOT / 'plugins.d')

os.environ['CONNECT_FIXTURE_MODE'] = sys.argv[1]
original = confconsole.plugin.PluginManager


def manager(path, globals):
    result = original(str(ROOT / 'plugins.d'), globals)
    for item in result.path_map.values():
        if isinstance(item, confconsole.plugin.Plugin) and item.real_name == 'hub_services.py':
            item.module.CONNECT = str(ROOT / 'tests/shared_connect_fixture.py')
            item.module.invoke = lambda *args: {'status': 'disconnected'}
    return result


confconsole.plugin.PluginManager = manager
sys.argv = ['confconsole']
confconsole.main()
print('FINISHED')
