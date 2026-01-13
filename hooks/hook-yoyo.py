# Hook personalizado para yoyo-migrations
# Garante que todos os backends e submódulos sejam incluídos

from PyInstaller.utils.hooks import collect_submodules, collect_data_files
import yoyo.backends

# Coleta todos os submódulos do yoyo
hiddenimports = collect_submodules('yoyo')

# Adiciona backends específicos que existem
hiddenimports += [
    'yoyo.backends',
    'yoyo.backends.base',
    'yoyo.backends.core',
    'yoyo.backends.core.sqlite3',
    'yoyo.backends.core.mysql',
    'yoyo.backends.core.postgresql',
    'yoyo.migrations',
    'yoyo.exceptions',
    'yoyo.connections',
    'sqlite3',  # MÓDULO SQLITE3 DO PYTHON
]

# Coleta arquivos de dados se houver
datas = collect_data_files('yoyo')

# Garante que os entry points do yoyo sejam registrados
try:
    import pkg_resources
    # Força o registro dos entry points do yoyo
    pkg_resources.get_entry_info('yoyo-migrations', 'yoyo.backends', 'sqlite')
except:
    pass
