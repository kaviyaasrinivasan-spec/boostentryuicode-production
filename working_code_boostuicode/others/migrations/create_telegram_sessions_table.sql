-- Create table for pending Telegram sessions
CREATE TABLE IF NOT EXISTS telegram_pending_sessions (
    id SERIAL PRIMARY KEY,
    doc_id INTEGER NOT NULL,
    phone_no VARCHAR(20) NOT NULL,
    chat_id VARCHAR(50),
    manifest_no VARCHAR(50),
    advance_amount DECIMAL(15, 2),
    qty DECIMAL(15, 3),
    status VARCHAR(20) DEFAULT 'pending', -- pending, waiting_advance, waiting_qty, completed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (doc_id) REFERENCES doc_processing_log(doc_id)
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_telegram_sessions_chat_id ON telegram_pending_sessions(chat_id);
CREATE INDEX IF NOT EXISTS idx_telegram_sessions_status ON telegram_pending_sessions(status);
