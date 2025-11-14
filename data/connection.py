import sqlite3
import os
import threading
import time
from utils import get_data_path
import logging

DB_FILE = get_data_path('pdv.db')

class DatabaseConnectionPool:
    """
    Pool de conexões SQLite para otimizar o uso de conexões e reduzir logs excessivos.
    Mantém um pool de conexões reutilizáveis e gerencia automaticamente a criação e limpeza.
    """

    def __init__(self, max_connections=5, connection_timeout=300):
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout  # 5 minutos por padrão
        self._pool = []
        self._lock = threading.RLock()
        self._connection_count = 0
        self._last_log_time = 0
        self._log_interval = 60  # Log a cada 60 segundos para reduzir verbosidade

    def get_connection(self):
        """Obtém uma conexão do pool ou cria uma nova se necessário."""
        with self._lock:
            # Tentar reutilizar uma conexão existente
            current_time = time.time()
            for conn_info in self._pool[:]:  # Copiar lista para evitar problemas de modificação
                conn, created_time, in_use = conn_info

                # Verificar se a conexão ainda é válida (não expirou)
                if current_time - created_time > self.connection_timeout:
                    try:
                        conn.close()
                    except:
                        pass
                    self._pool.remove(conn_info)
                    self._connection_count -= 1
                    continue

                # Verificar se a conexão não está em uso
                if not in_use:
                    conn_info[2] = True  # Marcar como em uso
                    return conn

            # Se não encontrou conexão disponível, criar uma nova
            if self._connection_count < self.max_connections:
                conn = self._create_connection()
                self._pool.append([conn, current_time, True])  # [conn, created_time, in_use]
                self._connection_count += 1

                # Log reduzido para evitar spam - apenas uma vez por hora
                if current_time - self._last_log_time > 3600:  # 1 hora
                    logging.info(f"DatabaseConnectionPool: Nova conexão criada (total: {self._connection_count})")
                    self._last_log_time = current_time

                return conn

            # Se atingiu o limite máximo, criar uma conexão temporária (não pool)
            # Log apenas uma vez por hora para evitar spam
            if current_time - self._last_log_time > 3600:
                logging.warning("DatabaseConnectionPool: Limite máximo atingido, criando conexão temporária")
                self._last_log_time = current_time
            return self._create_connection()

    def release_connection(self, conn):
        """Libera uma conexão de volta para o pool."""
        with self._lock:
            for conn_info in self._pool:
                if conn_info[0] is conn:
                    conn_info[2] = False  # Marcar como não em uso
                    break

    def close_all(self):
        """Fecha todas as conexões do pool."""
        with self._lock:
            for conn_info in self._pool:
                try:
                    conn_info[0].close()
                except:
                    pass
            self._pool.clear()
            self._connection_count = 0
            logging.debug("DatabaseConnectionPool: Todas as conexões fechadas")

    def _create_connection(self):
        """Cria uma nova conexão com as configurações padrão."""
        conn = sqlite3.connect(DB_FILE)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode=WAL")  # Melhora a concorrência e escrita
        conn.row_factory = sqlite3.Row
        return conn

    def get_stats(self):
        """Retorna estatísticas do pool."""
        with self._lock:
            in_use = sum(1 for conn_info in self._pool if conn_info[2])
            return {
                'total_connections': self._connection_count,
                'in_use': in_use,
                'available': self._connection_count - in_use,
                'max_connections': self.max_connections
            }


# Instância global do pool de conexões
_connection_pool = DatabaseConnectionPool()

def get_db_connection():
    """
    Obtém uma conexão com o banco de dados usando o pool de conexões.
    Retorna uma conexão SQLite configurada.
    """
    return _connection_pool.get_connection()

def release_db_connection(conn):
    """
    Libera uma conexão de volta para o pool.
    Deve ser chamada após o uso da conexão.
    """
    _connection_pool.release_connection(conn)

def close_connection_pool():
    """Fecha todas as conexões do pool (usar na finalização da aplicação)."""
    _connection_pool.close_all()

def get_connection_pool_stats():
    """Retorna estatísticas do pool de conexões."""
    return _connection_pool.get_stats()

class DatabaseConnection:
    """
    Context manager para conexões do banco de dados.
    Garante que a conexão seja liberada automaticamente após o uso.
    """

    def __init__(self):
        self.conn = None

    def __enter__(self):
        self.conn = get_db_connection()
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            release_db_connection(self.conn)
        return False

def get_db_connection_context():
    """
    Retorna um context manager para uso com 'with'.
    Exemplo: with get_db_connection_context() as conn: ...
    """
    return DatabaseConnection()

# Função de compatibilidade para código existente
def get_db_connection_old():
    """Versão antiga da função (mantida para compatibilidade)."""
    logging.debug(f"DEBUG: get_db_connection - Connecting to DB_FILE: {DB_FILE}")
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn
