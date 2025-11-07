
-- Step 1: Create the new sale_payments table
CREATE TABLE IF NOT EXISTS sale_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    payment_method TEXT NOT NULL,
    amount INTEGER NOT NULL,
    FOREIGN KEY (sale_id) REFERENCES sales (id) ON DELETE CASCADE
);

-- Step 2: Rename the original sales table
ALTER TABLE sales RENAME TO sales_old;

-- Step 3: Create the new sales table without the payment_method column
CREATE TABLE sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_amount INTEGER NOT NULL,
    user_id INTEGER,
    cash_session_id INTEGER,
    training_mode BOOLEAN DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (cash_session_id) REFERENCES cash_sessions (id)
);

-- Step 4: Copy data from the old table to the new one
-- Note: This assumes the python script will handle the logic of parsing the payment_method string and inserting into sale_payments.
-- yoyo-migrations can't do that directly. So, we'll just copy the sales data here.
INSERT INTO sales (id, sale_date, total_amount, user_id, cash_session_id, training_mode)
SELECT id, sale_date, total_amount, user_id, cash_session_id, training_mode
FROM sales_old;

-- Step 5: Drop the old sales table
DROP TABLE sales_old;

-- Step 6: Create index for the new table
CREATE INDEX IF NOT EXISTS idx_sale_payments_sale_id ON sale_payments (sale_id);
