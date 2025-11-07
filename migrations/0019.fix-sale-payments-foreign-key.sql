-- Recria a tabela sale_payments para garantir que a chave estrangeira aponta para a tabela correta (payment_methods)
-- Esta versão converte os dados de texto antigos (ex: 'Dinheiro') para os IDs numéricos corretos.

PRAGMA foreign_keys=off;

-- 1. Crie uma tabela temporária com a estrutura correta
CREATE TABLE sale_payments_temp (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    payment_method INTEGER NOT NULL, -- Garante que é INTEGER
    amount INTEGER NOT NULL,
    FOREIGN KEY (sale_id) REFERENCES sales (id) ON DELETE CASCADE,
    FOREIGN KEY (payment_method) REFERENCES payment_methods (id) -- Aponte para a tabela CORRETA
);

-- 2. Copie e TRANSFORME os dados da tabela antiga para a nova
-- Isso garante que os nomes de texto sejam convertidos para os IDs correspondentes.
INSERT INTO sale_payments_temp (id, sale_id, payment_method, amount)
SELECT 
    id, 
    sale_id, 
    CASE 
        WHEN lower(payment_method) = 'dinheiro' THEN 1
        WHEN lower(payment_method) = 'pix' THEN 2
        WHEN lower(payment_method) = 'débito' THEN 3
        WHEN lower(payment_method) = 'crédito' THEN 4
        ELSE 1 -- Fallback para Dinheiro caso exista algum outro valor inesperado
    END, 
    amount 
FROM sale_payments;

-- 3. Remova a tabela antiga e corrompida
DROP TABLE sale_payments;

-- 4. Renomeie a tabela temporária para o nome original
ALTER TABLE sale_payments_temp RENAME TO sale_payments;

PRAGMA foreign_keys=on;