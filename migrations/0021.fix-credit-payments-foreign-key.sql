-- Step 1: Disable foreign key constraints
PRAGMA foreign_keys=off;

-- Step 2: Create a new table with the correct foreign key
CREATE TABLE credit_payments_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    credit_sale_id INTEGER NOT NULL,
    amount_paid INTEGER NOT NULL,
    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL,
    payment_method TEXT NOT NULL,
    cash_session_id INTEGER,
    id_web TEXT UNIQUE,
    sync_status TEXT NOT NULL DEFAULT 'pending_create',
    is_deleted BOOLEAN NOT NULL DEFAULT 0,
    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (credit_sale_id) REFERENCES credit_sales(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (cash_session_id) REFERENCES cash_sessions(id) ON DELETE SET NULL
);

-- Step 3: Copy data from the old table to the new one
INSERT INTO credit_payments_new (id, credit_sale_id, amount_paid, payment_date, user_id, payment_method, cash_session_id, id_web, sync_status, is_deleted, last_modified)
SELECT id, credit_sale_id, amount_paid, payment_date, user_id, payment_method, cash_session_id, id_web, sync_status, is_deleted, last_modified
FROM credit_payments;

-- Step 4: Drop the old table
DROP TABLE credit_payments;

-- Step 5: Rename the new table
ALTER TABLE credit_payments_new RENAME TO credit_payments;

-- Step 6: Recreate indexes on the new table (if any)
CREATE INDEX IF NOT EXISTS idx_credit_payments_credit_sale_id ON credit_payments (credit_sale_id);
CREATE INDEX IF NOT EXISTS idx_credit_payments_user_id ON credit_payments (user_id);

-- Step 7: Enable foreign key constraints
PRAGMA foreign_keys=on;
