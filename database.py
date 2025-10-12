# database.py - Módulo Fachada (Facade)
# Este arquivo re-exporta funções do novo pacote 'data' para manter
# a compatibilidade com o resto da aplicação.

# Setup
from data.connection import get_db_connection, DB_FILE
from data.schema import create_tables

# Repositórios
from data.admin_repository import *
from data.audit_repository import *
from data.cash_repository import *
from data.credit_repository import *
from data.group_repository import *
from data.inventory_repository import *
from data.payment_method_repository import *
from data.product_repository import *
from data.reports_repository import *
from data.sale_repository import *
from data.user_repository import *
from data.settings_repository import *

# Funções que não se encaixam em outros módulos (se houver alguma restante)
# ...
