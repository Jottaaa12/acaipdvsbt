# PyInstaller hook for yoyo-migrations
#
# The 'yoyo.migrations' and 'yoyo.backends' entry points are modules that
# contain the migrations and database backends respectively. We need to add
# them to hiddenimports so that PyInstaller bundles them.
from importlib.metadata import entry_points
from PyInstaller.utils.hooks import collect_data_files

hiddenimports = []

for group in ['yoyo.migrations', 'yoyo.backends']:
    try:
        # importlib.metadata.entry_points returns a SelectableGroups object in Python 3.10+
        eps = entry_points(group=group)
    except TypeError:
        # Prior to Python 3.10, entry_points returned a dict
        eps = entry_points().get(group, [])
    hiddenimports.extend(ep.module for ep in eps)

# The backends also have data files (the drivers themselves) that need to be
# collected.
datas = collect_data_files('yoyo', include_py_files=True)
