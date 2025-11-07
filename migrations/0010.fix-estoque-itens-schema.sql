
-- Step 1: Rename old table
ALTER TABLE estoque_itens RENAME TO estoque_itens_old;

-- Step 2: Create new table with correct schema
CREATE TABLE estoque_itens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE NOT NULL,
    nome TEXT NOT NULL,
    grupo_id INTEGER NOT NULL,
    estoque_atual INTEGER NOT NULL,
    estoque_minimo INTEGER NOT NULL DEFAULT 0,
    unidade_medida TEXT,
    FOREIGN KEY (grupo_id) REFERENCES estoque_grupos (id)
);

-- Step 3: Copy data from old table to new table
INSERT INTO estoque_itens (id, codigo, nome, grupo_id, estoque_atual, estoque_minimo, unidade_medida)
SELECT id, codigo, nome, grupo_id, estoque_atual, estoque_minimo, unidade_medida
FROM estoque_itens_old;

-- Step 4: Drop old table
DROP TABLE estoque_itens_old;
