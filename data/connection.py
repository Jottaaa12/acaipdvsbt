import sqlite3
import os
from utils import get_data_path
import logging

DB_FILE = get_data_path('pdv.db')

def get_db_connection():
    """Cria e retorna uma conexão com o banco de dados."""
    logging.debug(f"DEBUG: get_db_connection - Connecting to DB_FILE: {DB_FILE}")
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL") # Melhora a concorrência e escrita
    conn.row_factory = sqlite3.Row
    return conn
