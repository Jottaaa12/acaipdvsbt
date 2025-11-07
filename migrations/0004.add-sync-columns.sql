
-- Add sync columns to product_groups
ALTER TABLE product_groups ADD COLUMN id_web TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_product_groups_id_web_unique ON product_groups(id_web);
ALTER TABLE product_groups ADD COLUMN sync_status TEXT NOT NULL DEFAULT 'pending_create';
ALTER TABLE product_groups ADD COLUMN last_modified_at TIMESTAMP;
UPDATE product_groups SET last_modified_at = CURRENT_TIMESTAMP;

-- Add sync columns to products
ALTER TABLE products ADD COLUMN id_web TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_products_id_web_unique ON products(id_web);
ALTER TABLE products ADD COLUMN sync_status TEXT NOT NULL DEFAULT 'pending_create';
ALTER TABLE products ADD COLUMN last_modified_at TIMESTAMP;
UPDATE products SET last_modified_at = CURRENT_TIMESTAMP;

-- Add sync columns to payment_methods
ALTER TABLE payment_methods ADD COLUMN id_web TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_payment_methods_id_web_unique ON payment_methods(id_web);
ALTER TABLE payment_methods ADD COLUMN sync_status TEXT NOT NULL DEFAULT 'pending_create';
ALTER TABLE payment_methods ADD COLUMN last_modified_at TIMESTAMP;
UPDATE payment_methods SET last_modified_at = CURRENT_TIMESTAMP;

-- Add sync columns to users
ALTER TABLE users ADD COLUMN id_web TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_id_web_unique ON users(id_web);
ALTER TABLE users ADD COLUMN sync_status TEXT NOT NULL DEFAULT 'pending_create';
ALTER TABLE users ADD COLUMN last_modified_at TIMESTAMP;
UPDATE users SET last_modified_at = CURRENT_TIMESTAMP;

-- Add sync columns to customers
ALTER TABLE customers ADD COLUMN id_web TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_id_web_unique ON customers(id_web);
ALTER TABLE customers ADD COLUMN sync_status TEXT NOT NULL DEFAULT 'pending_create';
ALTER TABLE customers ADD COLUMN last_modified_at TIMESTAMP;
UPDATE customers SET last_modified_at = CURRENT_TIMESTAMP;

-- Add sync columns to sales
ALTER TABLE sales ADD COLUMN id_web TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_sales_id_web_unique ON sales(id_web);
ALTER TABLE sales ADD COLUMN sync_status TEXT NOT NULL DEFAULT 'pending_create';
ALTER TABLE sales ADD COLUMN last_modified_at TIMESTAMP;
UPDATE sales SET last_modified_at = CURRENT_TIMESTAMP;

-- Add sync columns to sale_items
ALTER TABLE sale_items ADD COLUMN id_web TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_sale_items_id_web_unique ON sale_items(id_web);
ALTER TABLE sale_items ADD COLUMN sync_status TEXT NOT NULL DEFAULT 'pending_create';
ALTER TABLE sale_items ADD COLUMN last_modified_at TIMESTAMP;
UPDATE sale_items SET last_modified_at = CURRENT_TIMESTAMP;

-- Add sync columns to credit_sales
ALTER TABLE credit_sales ADD COLUMN id_web TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_credit_sales_id_web_unique ON credit_sales(id_web);
ALTER TABLE credit_sales ADD COLUMN sync_status TEXT NOT NULL DEFAULT 'pending_create';
ALTER TABLE credit_sales ADD COLUMN last_modified_at TIMESTAMP;
UPDATE credit_sales SET last_modified_at = CURRENT_TIMESTAMP;

-- Add sync columns to credit_payments
ALTER TABLE credit_payments ADD COLUMN id_web TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_credit_payments_id_web_unique ON credit_payments(id_web);
ALTER TABLE credit_payments ADD COLUMN sync_status TEXT NOT NULL DEFAULT 'pending_create';
ALTER TABLE credit_payments ADD COLUMN last_modified_at TIMESTAMP;
UPDATE credit_payments SET last_modified_at = CURRENT_TIMESTAMP;

-- Add sync columns to estoque_grupos
ALTER TABLE estoque_grupos ADD COLUMN id_web TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_estoque_grupos_id_web_unique ON estoque_grupos(id_web);
ALTER TABLE estoque_grupos ADD COLUMN sync_status TEXT NOT NULL DEFAULT 'pending_create';
ALTER TABLE estoque_grupos ADD COLUMN last_modified_at TIMESTAMP;
UPDATE estoque_grupos SET last_modified_at = CURRENT_TIMESTAMP;

-- Add sync columns to estoque_itens
ALTER TABLE estoque_itens ADD COLUMN id_web TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_estoque_itens_id_web_unique ON estoque_itens(id_web);
ALTER TABLE estoque_itens ADD COLUMN sync_status TEXT NOT NULL DEFAULT 'pending_create';
ALTER TABLE estoque_itens ADD COLUMN last_modified_at TIMESTAMP;
UPDATE estoque_itens SET last_modified_at = CURRENT_TIMESTAMP;

-- Add sync columns to cash_sessions
ALTER TABLE cash_sessions ADD COLUMN id_web TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_cash_sessions_id_web_unique ON cash_sessions(id_web);
ALTER TABLE cash_sessions ADD COLUMN sync_status TEXT NOT NULL DEFAULT 'pending_create';
ALTER TABLE cash_sessions ADD COLUMN last_modified_at TIMESTAMP;
UPDATE cash_sessions SET last_modified_at = CURRENT_TIMESTAMP;
