-- Corrigir chave estrangeira da tabela sale_items para apontar para products em vez de products_old

-- Primeiro, remover a chave estrangeira incorreta
-- Como o SQLite não suporta DROP CONSTRAINT diretamente, precisamos recriar a tabela

-- Criar tabela temporária com a estrutura correta
CREATE TABLE sale_items_temp (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity REAL NOT NULL,
    unit_price INTEGER NOT NULL,
    total_price INTEGER NOT NULL,
    peso_kg REAL,
    id_web TEXT UNIQUE,
    sync_status TEXT NOT NULL DEFAULT 'pending_create',
    is_deleted BOOLEAN NOT NULL DEFAULT 0,
    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sale_id) REFERENCES sales (id),
    FOREIGN KEY (product_id) REFERENCES products (id)
);

-- Copiar dados da tabela antiga para a nova
INSERT INTO sale_items_temp (id, sale_id, product_id, quantity, unit_price, total_price, peso_kg, id_web, sync_status, is_deleted, last_modified)
SELECT id, sale_id, product_id, quantity, unit_price, total_price, peso_kg, id_web, sync_status, is_deleted, last_modified
FROM sale_items;

-- Remover tabela antiga
DROP TABLE sale_items;

-- Renomear tabela temporária para o nome original
ALTER TABLE sale_items_temp RENAME TO sale_items;

-- Recriar índices
CREATE INDEX IF NOT EXISTS idx_sale_items_sale_id ON sale_items (sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_product_id ON sale_items (product_id);
