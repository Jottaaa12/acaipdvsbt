CREATE TABLE IF NOT EXISTS sales_old (
    id INTEGER PRIMARY KEY,
    sale_date TIMESTAMP,
    total_amount INTEGER,
    change_amount INTEGER,
    user_id INTEGER,
    cash_session_id INTEGER,
    training_mode BOOLEAN,
    id_web TEXT,
    sync_status TEXT,
    is_deleted BOOLEAN,
    last_modified TIMESTAMP,
    session_sale_id INTEGER,
    customer_name TEXT
);