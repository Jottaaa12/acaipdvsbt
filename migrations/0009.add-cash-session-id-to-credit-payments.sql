
ALTER TABLE credit_payments ADD COLUMN cash_session_id INTEGER REFERENCES cash_sessions(id) ON DELETE SET NULL;
