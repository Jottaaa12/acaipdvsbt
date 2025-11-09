import logging
import sqlite3
from typing import Dict
from datetime import datetime, timezone # <-- ADICIONAR
from .connection import get_db_connection
from .api_client import api_client_instance
from data.settings_repository import SettingsRepository # <-- ADICIONAR
from PyQt6.QtCore import QObject, pyqtSignal
from postgrest import APIResponse

# Define a ordem exata de sincronização, de pais para filhos.
SYNC_ORDER = [
    # Independentes (Nível 0)
    'product_groups',
    'estoque_grupos',
    'payment_methods',
    'users',
    'customers',

    # Dependentes (Nível 1)
    'cash_sessions',  # Depende de 'users'
    'products',       # Depende de 'product_groups'
    'estoque_itens',  # Depende de 'estoque_grupos'

    # Dependentes (Nível 2)
    'sales',          # Depende de 'users', 'cash_sessions', 'customers'

    # Dependentes (Nível 3)
    'sale_items',     # Depende de 'sales', 'products'
    'credit_sales',   # Depende de 'customers', 'sales', 'users'

    # Dependentes (Nível 4)
    'credit_payments' # Depende de 'credit_sales', 'users', 'cash_sessions'
]

SYNC_TABLES_INDEPENDENT = [
    'product_groups',
    'estoque_grupos',
    'payment_methods',
    'users',
    'customers',
]

# Mapeia tabelas para suas colunas de CONFLITO (chave única)
CONFLICT_COLUMNS: Dict[str, str] = {
    'product_groups': 'name',
    'estoque_grupos': 'nome',
    'payment_methods': 'name',
    'customers': 'cpf',
    'users': 'username',
    'products': 'barcode', # Conflito em 'barcode'
    'estoque_itens': 'codigo', # Conflito em 'codigo'
    # Tabelas transacionais (sales, sale_items, etc.) não têm
    # chaves únicas de negócio, elas serão apenas INSERT.
}

class SyncManager(QObject):
    """
    Gerencia a sincronização de dados (upload e download)
    entre o banco de dados SQLite local e a API web (Supabase).

    Emite sinais para a UI atualizar o status.
    """
    sync_status_updated = pyqtSignal(str) # Sinal para enviar mensagens de status
    sync_finished = pyqtSignal(bool, str) # Sinal (sucesso, mensagem)

    def __init__(self):
        super().__init__()
        self.api_client = api_client_instance
        self.settings_repo = SettingsRepository() # <-- ADICIONAR
        self.is_syncing = False

    def check_connection_and_run_sync(self):
        """
        Ponto de entrada principal. Verifica a conexão e inicia a sincronização
        se não estiver ocupado.
        """
        if self.is_syncing:
            logging.warning("SyncManager: Tentativa de iniciar sincronização enquanto outra já está em andamento.")
            self.sync_status_updated.emit("Sincronização já em andamento...")
            return

        if not self.api_client.check_connection():
            logging.warning("SyncManager: Sincronização falhou. Sem conexão com a API.")
            self.sync_finished.emit(False, "Falha na conexão. Verifique a internet e o Supabase.")
            return

        self.is_syncing = True
        self.sync_status_updated.emit("Iniciando sincronização...")

        try:
            # Define o carimbo de data/hora ANTES de qualquer operação
            # Usamos UTC (padrão do Supabase)
            new_sync_timestamp = datetime.now(timezone.utc).isoformat()

            # 1. Enviar criações pendentes (Upload)
            self._sync_pending_creates()

            # 2. Enviar atualizações pendentes (Upload)
            self._sync_pending_updates()

            # 3. Baixar mudanças da web (Download)
            self._sync_web_to_local(new_sync_timestamp)

            # 4. Se tudo deu certo, salva o novo timestamp
            self.settings_repo.save_setting('last_sync_timestamp', new_sync_timestamp)

            logging.info("SyncManager: Sincronização concluída com sucesso.")
            self.sync_finished.emit(True, f"Sincronização concluída (Até {new_sync_timestamp}).")

        except Exception as e:
            logging.error(f"SyncManager: Erro crítico durante a sincronização: {e}", exc_info=True)
            self.sync_finished.emit(False, f"Erro na sincronização: {e}")
        finally:
            self.is_syncing = False

    def _sync_pending_creates(self):
        """
        Passo 1: Processa todos os registros com 'pending_create'
        Envia para o Supabase e salva o 'id_web' localmente.
        """
        logging.info("SyncManager: Iniciando _sync_pending_creates...")
        self.sync_status_updated.emit("Enviando novos registros...")

        conn = get_db_connection()
        conn.row_factory = sqlite3.Row # Garante que possamos acessar por nome de coluna
        cursor = conn.cursor()

        # Cache para armazenar id_web já consultados (performance)
        web_id_cache = {}

        # Processa todas as tabelas na ordem definida
        for table_name in SYNC_ORDER:
            try:
                cursor.execute(f"SELECT * FROM {table_name} WHERE sync_status = 'pending_create' ORDER BY id")
                rows_to_create = cursor.fetchall()

                if not rows_to_create:
                    continue

                logging.info(f"SyncManager: Encontrados {len(rows_to_create)} registros 'pending_create' em '{table_name}'")
                self.sync_status_updated.emit(f"Enviando {len(rows_to_create)} itens de '{table_name}'...")

                payloads = []
                local_ids = []

                for row in rows_to_create:
                    payload = self._build_payload(conn, web_id_cache, table_name, row)
                    if payload is None:
                        # Dependência obrigatória não sincronizada, pula este registro
                        logging.warning(f"SyncManager: Pulando registro {row['id']} de '{table_name}' devido a dependência não sincronizada")
                        continue

                    payloads.append(payload)
                    local_ids.append(row['id'])

                if not payloads:
                    # Nenhum payload válido para esta tabela
                    continue

                # Verifica se existe uma coluna de conflito para usar upsert
                conflict_column = CONFLICT_COLUMNS.get(table_name)

                if conflict_column:
                    # Usa upsert se houver coluna de conflito definida
                    api_response = self.api_client.get_client().table(table_name).upsert(payloads, on_conflict=conflict_column).execute()
                else:
                    # Usa insert normal se não houver coluna de conflito
                    api_response = self.api_client.get_client().table(table_name).insert(payloads).execute()

                if not isinstance(api_response, APIResponse) or not api_response.data:
                    raise Exception(f"Falha ao inserir em '{table_name}': Resposta inválida da API.")

                # Se sucesso, atualiza o status local
                update_data = []
                for i, new_record in enumerate(api_response.data):
                    local_id = local_ids[i]
                    web_id = new_record['id'] # O 'id' do Supabase
                    update_data.append((str(web_id), local_id))

                cursor.executemany(
                    f"UPDATE {table_name} SET id_web = ?, sync_status = 'synced' WHERE id = ?",
                    update_data
                )
                conn.commit()
                logging.info(f"SyncManager: {len(update_data)} registros de '{table_name}' criados na web e atualizados localmente.")

            except Exception as e:
                logging.error(f"SyncManager: Erro ao processar 'pending_create' para tabela {table_name}: {e}", exc_info=True)
                self.sync_status_updated.emit(f"Erro ao enviar '{table_name}': {e}")
                conn.rollback() # Desfaz alterações desta tabela
                # Continua para a próxima tabela

        conn.close()

    def _sync_pending_updates(self):
        """
        Passo 2: Processa todos os registros com 'pending_update'
        Atualiza no Supabase usando o 'id_web'.
        """
        logging.info("SyncManager: Iniciando _sync_pending_updates...")
        self.sync_status_updated.emit("Atualizando registros...")

        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Cache para armazenar id_web já consultados (performance)
        web_id_cache = {}

        # Processa todas as tabelas na ordem definida
        for table_name in SYNC_ORDER:
            try:
                # Pegamos apenas os que têm 'pending_update' E já têm um 'id_web'
                cursor.execute(f"SELECT * FROM {table_name} WHERE sync_status = 'pending_update' AND id_web IS NOT NULL ORDER BY id")
                rows_to_update = cursor.fetchall()

                if not rows_to_update:
                    continue

                logging.info(f"SyncManager: Encontrados {len(rows_to_update)} registros 'pending_update' em '{table_name}'")
                self.sync_status_updated.emit(f"Atualizando {len(rows_to_update)} itens de '{table_name}'...")

                for row in rows_to_update:
                    local_id = row['id']
                    web_id = row['id_web']
                    payload = self._build_payload(conn, web_id_cache, table_name, row)

                    if payload is None:
                        # Dependência obrigatória não sincronizada, pula este registro
                        logging.warning(f"SyncManager: Pulando atualização do registro {local_id} de '{table_name}' devido a dependência não sincronizada")
                        continue

                    try:
                        # Envia 1 por 1 para atualização
                        self.api_client.get_client().table(table_name).update(payload).eq('id', web_id).execute()

                        # Se sucesso, atualiza o status local
                        cursor.execute(f"UPDATE {table_name} SET sync_status = 'synced' WHERE id = ?", (local_id,))

                    except Exception as e:
                        logging.error(f"SyncManager: Falha ao atualizar item {local_id} (web_id: {web_id}) em '{table_name}': {e}", exc_info=True)
                        self.sync_status_updated.emit(f"Erro ao atualizar item em '{table_name}'")
                        # Não para o loop, tenta o próximo item

                conn.commit() # Commita os sucessos do loop

            except Exception as e:
                logging.error(f"SyncManager: Erro ao processar 'pending_update' para tabela {table_name}: {e}", exc_info=True)
                conn.rollback()
                # Continua para a próxima tabela

        conn.close()

    def _sync_web_to_local(self, new_sync_timestamp: str):
        """
        Passo 3: Processa dados da web (Supabase) e os insere/atualiza
        no banco de dados local (SQLite).
        """
        logging.info("SyncManager: Iniciando _sync_web_to_local...")
        self.sync_status_updated.emit("Baixando atualizações...")

        last_sync_timestamp = self.settings_repo.get_setting('last_sync_timestamp')
        if not last_sync_timestamp:
            last_sync_timestamp = '1970-01-01T00:00:00+00:00' # Fallback

        logging.info(f"SyncManager: Buscando alterações entre {last_sync_timestamp} e {new_sync_timestamp}")

        conn = get_db_connection()
        cursor = conn.cursor()
        local_id_cache = {} # Cache para _get_local_id

        # Loop na ordem de sincronização (pais primeiro)
        for table_name in SYNC_ORDER:
            try:
                # 1. Busca dados da web que mudaram
                self.sync_status_updated.emit(f"Verificando '{table_name}'...")
                api_response = self.api_client.get_client().table(table_name).select("*") \
                    .gt("updated_at", last_sync_timestamp) \
                    .lt("updated_at", new_sync_timestamp) \
                    .execute()

                if not isinstance(api_response, APIResponse) or not api_response.data:
                    continue

                data_from_web = api_response.data
                logging.info(f"SyncManager: Recebidos {len(data_from_web)} registros atualizados de '{table_name}'.")

                # 2. Processa cada registro (Insere ou Atualiza localmente)
                for web_record in data_from_web:
                    web_id = web_record['id']

                    # Constrói o payload (Por enquanto, sem tradução de FK)
                    payload = self._build_local_payload(conn, local_id_cache, table_name, web_record)
                    if not payload:
                        logging.warning(f"SyncManager: Falha ao construir payload local para {table_name} (web_id: {web_id}). Pulando.")
                        continue

                    # Verifica se o registro já existe localmente
                    cursor.execute(f"SELECT id FROM {table_name} WHERE id_web = ?", (str(web_id),))
                    local_record = cursor.fetchone()

                    # Adiciona o id_web e sync_status ao payload
                    payload['id_web'] = str(web_id)
                    payload['sync_status'] = 'synced'

                    if local_record:
                        # --- UPDATE LOCAL ---
                        local_id = local_record[0]

                        # Garantir que o sync_status esteja 'synced' para não causar loop
                        payload['sync_status'] = 'synced'

                        # Remover chaves que não devem ser nulas se o valor for None
                        # (O _build_local_payload já fez a maior parte disso)
                        final_payload = {k: v for k, v in payload.items() if v is not None}

                        set_clause = ", ".join([f"{key} = ?" for key in final_payload.keys()])
                        values = list(final_payload.values()) + [local_id]

                        if not set_clause:
                            logging.warning(f"SyncManager: Pulando UPDATE local de {table_name} (id_web: {web_id}) pois não há campos para atualizar.")
                            continue

                        cursor.execute(f"UPDATE {table_name} SET {set_clause} WHERE id = ?", values)

                    else:
                        # --- INSERT LOCAL ---
                        # Agora habilitado para TODAS as tabelas, pois
                        # _build_local_payload traduz as FKs.

                        # Garantir que o sync_status esteja 'synced'
                        payload['sync_status'] = 'synced'
                        payload['id_web'] = str(web_id) # id_web é obrigatório no insert

                        # Remover chaves nulas que não têm valor padrão
                        final_payload = {k: v for k, v in payload.items() if v is not None}

                        columns = ", ".join(final_payload.keys())
                        placeholders = ", ".join(["?" for _ in final_payload.keys()])
                        values = list(final_payload.values())

                        if not columns:
                            logging.warning(f"SyncManager: Pulando INSERT local de {table_name} (id_web: {web_id}) pois não há campos para inserir.")
                            continue

                        cursor.execute(f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})", values)

                    # Commit para cada registro processado
                    conn.commit()

            except Exception as e:
                logging.error(f"SyncManager: Erro ao processar _sync_web_to_local para tabela {table_name}: {e}", exc_info=True)
                self.sync_status_updated.emit(f"Erro ao baixar '{table_name}': {e}")
                conn.rollback()

        conn.close()

    def _get_local_id(self, conn: sqlite3.Connection, cache: dict, table_name: str, web_id: str) -> int | None:
        """
        Busca o id local (SQLite) de um registro pai, usando o id_web.
        O INVERSO de _get_web_id.
        """
        if not web_id:
            return None

        cache_key = f"{table_name}_{web_id}"
        if cache_key in cache:
            return cache[cache_key]

        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT id FROM {table_name} WHERE id_web = ?", (web_id,))
            result = cursor.fetchone()

            if result and result['id']:
                cache[cache_key] = result['id']
                return result['id']
            else:
                return None # Pai não existe localmente (ainda)

        except Exception as e:
            logging.error(f"_get_local_id: Erro ao buscar id_local para {table_name} (web_id {web_id}): {e}")
            return None

    def _build_local_payload(self, conn: sqlite3.Connection, cache: dict, table_name: str, web_record: dict) -> dict | None:
        """
        Converte um registro vindo do Supabase (dict) em um payload
        limpo para inserir/atualizar no SQLite.
        
        Traduz chaves estrangeiras web (id) para chaves locais (id).
        Retorna None se uma dependência obrigatória não for encontrada.
        """
        payload = web_record.copy()
        
        # 1. Remover colunas de controle web
        payload.pop('id', None) # 'id' do Supabase
        payload.pop('created_at', None)
        payload.pop('updated_at', None)
        
        # 2. Limpar tipos de dados (Garantir INT para colunas BIGINT)
        # (Esta lógica foi movida para o final, após a tradução das FKs)

        try:
            # 3. Traduzir Chaves Estrangeiras (Web -> Local)
            if table_name == 'products':
                web_group_id = payload.pop('group_id', None)
                payload['group_id'] = self._get_local_id(conn, cache, 'product_groups', web_group_id)
            
            elif table_name == 'estoque_itens':
                web_group_id = payload.pop('grupo_id', None)
                payload['grupo_id'] = self._get_local_id(conn, cache, 'estoque_grupos', web_group_id)

            elif table_name == 'cash_sessions':
                web_user_id = payload.pop('user_id', None)
                payload['user_id'] = self._get_local_id(conn, cache, 'users', web_user_id)
                if not payload['user_id']: return None # Dependência obrigatória

            elif table_name == 'cash_movements':
                payload['session_id'] = self._get_local_id(conn, cache, 'cash_sessions', payload.pop('session_id', None))
                payload['user_id'] = self._get_local_id(conn, cache, 'users', payload.pop('user_id', None))
                payload['authorized_by_id'] = self._get_local_id(conn, cache, 'users', payload.pop('authorized_by_id', None))
                if not payload['session_id'] or not payload['user_id']: return None
            
            elif table_name == 'cash_counts':
                payload['session_id'] = self._get_local_id(conn, cache, 'cash_sessions', payload.pop('session_id', None))
                if not payload['session_id']: return None

            elif table_name == 'sales':
                payload['user_id'] = self._get_local_id(conn, cache, 'users', payload.pop('user_id', None))
                payload['cash_session_id'] = self._get_local_id(conn, cache, 'cash_sessions', payload.pop('cash_session_id', None))
                if not payload['user_id'] or not payload['cash_session_id']: return None

            elif table_name == 'sale_payments':
                payload['sale_id'] = self._get_local_id(conn, cache, 'sales', payload.pop('sale_id', None))
                if not payload['sale_id']: return None

            elif table_name == 'sale_items':
                payload['sale_id'] = self._get_local_id(conn, cache, 'sales', payload.pop('sale_id', None))
                payload['product_id'] = self._get_local_id(conn, cache, 'products', payload.pop('product_id', None))
                if not payload['sale_id'] or not payload['product_id']: return None
            
            elif table_name == 'credit_sales':
                payload['customer_id'] = self._get_local_id(conn, cache, 'customers', payload.pop('customer_id', None))
                payload['sale_id'] = self._get_local_id(conn, cache, 'sales', payload.pop('sale_id', None))
                payload['user_id'] = self._get_local_id(conn, cache, 'users', payload.pop('user_id', None))
                if not payload['customer_id'] or not payload['user_id']: return None
            
            elif table_name == 'credit_payments':
                payload['credit_sale_id'] = self._get_local_id(conn, cache, 'credit_sales', payload.pop('credit_sale_id', None))
                payload['user_id'] = self._get_local_id(conn, cache, 'users', payload.pop('user_id', None))
                payload['cash_session_id'] = self._get_local_id(conn, cache, 'cash_sessions', payload.pop('cash_session_id', None))
                if not payload['credit_sale_id'] or not payload['user_id']: return None

            # 4. Limpar Tipos de Dados (Garantir INT para colunas INTEGER/BIGINT)
            # Isto é o oposto do _build_payload (upload)
            int_cols_by_table = {
                'products': ['price', 'stock', 'quantity'],
                'cash_sessions': ['initial_amount', 'final_amount', 'expected_amount', 'difference'],
                'cash_movements': ['amount'],
                'cash_counts': ['total_value', 'quantity'],
                'sales': ['total_amount', 'change_amount'],
                'sale_payments': ['amount'],
                'sale_items': ['unit_price', 'total_price'],
                'customers': ['credit_limit'],
                'credit_sales': ['amount'],
                'credit_payments': ['amount_paid'],
                'estoque_itens': ['estoque_atual', 'estoque_minimo']
            }
            
            if table_name in int_cols_by_table:
                for col in int_cols_by_table[table_name]:
                    if col in payload and payload[col] is not None:
                        try:
                            # O Supabase retorna valores BIGINT como int, 
                            # mas float (ex: NUMERIC) como string.
                            payload[col] = int(float(payload[col]))
                        except (ValueError, TypeError):
                            logging.error(f"Erro ao converter {col}='{payload[col]}' para int em {table_name}")
                            payload[col] = 0
            
            # Converte colunas 'REAL' (NUMERIC do Supabase)
            if table_name == 'sale_items' and 'quantity' in payload:
                 if payload['quantity'] is not None:
                    try:
                        payload['quantity'] = float(payload['quantity'])
                    except (ValueError, TypeError):
                        payload['quantity'] = 0.0

            # Remover quaisquer chaves que ficaram com valor None
            # O SQLite não gosta de "UPDATE table SET fk_id = NULL" se a coluna for NOT NULL
            keys_to_remove = [k for k, v in payload.items() if v is None]
            for k in keys_to_remove:
                 # Exceção: 'sale_id' em 'credit_sales' PODE ser nulo.
                if table_name == 'credit_sales' and k == 'sale_id':
                    continue
                # Exceção: 'authorized_by_id' em 'cash_movements' PODE ser nulo.
                if table_name == 'cash_movements' and k == 'authorized_by_id':
                    continue
                # Exceção: 'group_id' em 'products' PODE ser nulo.
                if table_name == 'products' and k == 'group_id':
                    continue
                # Exceção: 'grupo_id' em 'estoque_itens' PODE ser nulo (embora não devesse)
                if table_name == 'estoque_itens' and k == 'grupo_id':
                    continue

                logging.warning(f"Removendo chave '{k}' do payload local de '{table_name}' pois o valor é None.")
                payload.pop(k)

            return payload
            
        except Exception as e:
            logging.error(f"SyncManager: Erro ao construir payload local para {table_name} (Web Record: {web_record.get('id')}): {e}", exc_info=True)
            return None

    def _get_web_id(self, conn: sqlite3.Connection, cache: dict, table_name: str, local_id: int) -> str | None:
        """
        Busca o id_web de um registro pai, usando um cache para performance.
        """
        if not local_id:
            return None

        cache_key = f"{table_name}_{local_id}"
        if cache_key in cache:
            return cache[cache_key]

        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT id_web FROM {table_name} WHERE id = ?", (local_id,))
            result = cursor.fetchone()

            if result and result['id_web']:
                cache[cache_key] = result['id_web']
                return result['id_web']
            else:
                logging.warning(f"_get_web_id: Não foi possível encontrar id_web para {table_name} com local_id {local_id}. O pai precisa ser sincronizado primeiro.")
                return None

        except Exception as e:
            logging.error(f"_get_web_id: Erro ao buscar id_web para {table_name} (local_id {local_id}): {e}")
            return None

    def _build_payload(self, conn: sqlite3.Connection, cache: dict, table_name: str, row: sqlite3.Row) -> dict | None:
        """
        Converte uma linha do SQLite em um payload para o Supabase,
        traduzindo chaves estrangeiras locais para chaves web (id_web)
        e limpando os tipos de dados.

        Retorna None se uma dependência obrigatória não estiver sincronizada.
        """
        payload = dict(row)

        # 1. Remover colunas de controle local
        payload.pop('id', None)
        payload.pop('id_web', None)
        payload.pop('sync_status', None)
        payload.pop('last_modified_at', None)

        # 2. Remover colunas "virtuais" ou "JOINED" que não existem no Supabase
        if table_name == 'sales':
            payload.pop('customer_name', None) # Remove a coluna do JOIN
            payload.pop('user_name', None)     # Remove a coluna do JOIN (se existir)
            payload.pop('session_sale_id', None) # Remove a coluna que não existe no Supabase
        if table_name == 'products':
            payload.pop('group_name', None) # Remove a coluna do JOIN (se existir)
        if table_name == 'sale_items':
            payload.pop('peso_kg', None) # Remove a coluna que não existe no Supabase

        try:
            # 3. Traduzir Chaves Estrangeiras (FKs)
            if table_name == 'products':
                local_group_id = payload.pop('group_id', None)
                payload['group_id'] = self._get_web_id(conn, cache, 'product_groups', local_group_id)

            elif table_name == 'estoque_itens':
                local_group_id = payload.pop('grupo_id', None)
                payload['grupo_id'] = self._get_web_id(conn, cache, 'estoque_grupos', local_group_id)

            elif table_name == 'cash_sessions':
                local_user_id = payload.pop('user_id', None)
                payload['user_id'] = self._get_web_id(conn, cache, 'users', local_user_id)
                if not payload['user_id']: return None # Dependência obrigatória

            elif table_name == 'cash_movements':
                payload['session_id'] = self._get_web_id(conn, cache, 'cash_sessions', payload.pop('session_id', None))
                payload['user_id'] = self._get_web_id(conn, cache, 'users', payload.pop('user_id', None))
                payload['authorized_by_id'] = self._get_web_id(conn, cache, 'users', payload.pop('authorized_by_id', None))
                if not payload['session_id'] or not payload['user_id']: return None

            elif table_name == 'cash_counts':
                payload['session_id'] = self._get_web_id(conn, cache, 'cash_sessions', payload.pop('session_id', None))
                if not payload['session_id']: return None

            elif table_name == 'sales':
                payload['user_id'] = self._get_web_id(conn, cache, 'users', payload.pop('user_id', None))
                payload['cash_session_id'] = self._get_web_id(conn, cache, 'cash_sessions', payload.pop('cash_session_id', None))
                if not payload['user_id'] or not payload['cash_session_id']: return None

            elif table_name == 'sale_payments':
                payload['sale_id'] = self._get_web_id(conn, cache, 'sales', payload.pop('sale_id', None))
                if not payload['sale_id']: return None

            elif table_name == 'sale_items':
                payload['sale_id'] = self._get_web_id(conn, cache, 'sales', payload.pop('sale_id', None))
                payload['product_id'] = self._get_web_id(conn, cache, 'products', payload.pop('product_id', None))
                if not payload['sale_id'] or not payload['product_id']: return None

            elif table_name == 'credit_sales':
                payload['customer_id'] = self._get_web_id(conn, cache, 'customers', payload.pop('customer_id', None))
                payload['sale_id'] = self._get_web_id(conn, cache, 'sales', payload.pop('sale_id', None))
                payload['user_id'] = self._get_web_id(conn, cache, 'users', payload.pop('user_id', None))
                if not payload['customer_id'] or not payload['user_id']: return None

            elif table_name == 'credit_payments':
                payload['credit_sale_id'] = self._get_web_id(conn, cache, 'credit_sales', payload.pop('credit_sale_id', None))
                payload['user_id'] = self._get_web_id(conn, cache, 'users', payload.pop('user_id', None))
                payload['cash_session_id'] = self._get_web_id(conn, cache, 'cash_sessions', payload.pop('cash_session_id', None))
                if not payload['credit_sale_id'] or not payload['user_id']: return None

            # 4. Limpar Tipos de Dados (Corrigir Erro 2)
            # Converte todos os valores monetários (bigint) para int()
            bigint_cols_by_table = {
                'products': ['price', 'stock', 'quantity'],
                'cash_sessions': ['initial_amount', 'final_amount', 'expected_amount', 'difference'],
                'cash_movements': ['amount'],
                'cash_counts': ['total_value'],
                'sales': ['total_amount', 'change_amount'],
                'sale_payments': ['amount'],
                'sale_items': ['unit_price', 'total_price'],
                'customers': ['credit_limit'],
                'credit_sales': ['amount'],
                'credit_payments': ['amount_paid']
            }

            if table_name in bigint_cols_by_table:
                for col in bigint_cols_by_table[table_name]:
                    if col in payload and payload[col] is not None:
                        try:
                            payload[col] = int(float(payload[col]))
                        except (ValueError, TypeError):
                            logging.error(f"Erro ao converter {col}='{payload[col]}' para int em {table_name}")
                            payload[col] = 0 # Define um padrão seguro

            # Converte colunas 'REAL' (NUMERIC no Supabase)
            if table_name == 'sale_items' and 'quantity' in payload:
                 if payload['quantity'] is not None:
                    payload['quantity'] = float(payload['quantity'])

            return payload

        except Exception as e:
            logging.error(f"SyncManager: Erro ao construir payload para {table_name} (Local ID: {row['id']}): {e}", exc_info=True)
            return None

    def truncate_supabase_data(self):
        """
        Chama uma função RPC no Supabase para truncar todas as tabelas transacionais.
        Retorna (True, "Sucesso") ou (False, "Mensagem de Erro").
        """
        try:
            logging.warning("Iniciando chamada RPC para truncate_transactional_data no Supabase.")
            self.sync_status_updated.emit("Enviando comando de limpeza para a nuvem...")

            # Chama a função SQL `truncate_transactional_data` no Supabase
            self.api_client.get_client().rpc('truncate_transactional_data', {}).execute()

            logging.info("Comando truncate_transactional_data executado com sucesso no Supabase.")
            self.sync_status_updated.emit("Dados da nuvem limpos com sucesso.")
            return True, "Dados transacionais da nuvem foram limpos com sucesso."

        except Exception as e:
            logging.error(f"Erro ao executar RPC truncate_transactional_data: {e}", exc_info=True)
            self.sync_status_updated.emit(f"Erro ao limpar dados da nuvem: {e}")
            return False, f"Erro ao executar a limpeza na nuvem: {e}"
