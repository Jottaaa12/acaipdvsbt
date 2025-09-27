'''
Script de migração para atualizar o esquema do banco de dados.
'''
import sqlite3

DB_FILE = 'pdv.db'

def run_migration():
    '''Executa as alterações necessárias no banco de dados.'''
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        print("Conectado ao banco de dados para migração.")

        # Adicionar a coluna authorized_by_id à tabela cash_movements
        try:
            cursor.execute('ALTER TABLE cash_movements ADD COLUMN authorized_by_id INTEGER REFERENCES users(id)')
            print("Coluna 'authorized_by_id' adicionada com sucesso à tabela 'cash_movements'.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("A coluna 'authorized_by_id' já existe em 'cash_movements'.")
            else:
                raise

        # Adicionar a coluna observations à tabela cash_sessions
        try:
            cursor.execute('ALTER TABLE cash_sessions ADD COLUMN observations TEXT')
            print("Coluna 'observations' adicionada com sucesso à tabela 'cash_sessions'.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("A coluna 'observations' já existe em 'cash_sessions'.")
            else:
                raise

        conn.commit()
        print("Migração do banco de dados concluída com sucesso.")

    except sqlite3.Error as e:
        print(f"Ocorreu um erro durante a migração do banco de dados: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            print("Conexão com o banco de dados fechada.")

if __name__ == '__main__':
    run_migration()
