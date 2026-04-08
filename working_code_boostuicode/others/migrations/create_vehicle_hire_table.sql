-- Create vehicle_hire table
CREATE TABLE IF NOT EXISTS vehicle_hire (
    id SERIAL PRIMARY KEY,
    doc_id INTEGER NOT NULL REFERENCES doc_processing_log(doc_id),
    manifest_no VARCHAR(100) NOT NULL,
    advance_amount DECIMAL(10, 2) NOT NULL,
    payable_at VARCHAR(100) NOT NULL,
    paid_by VARCHAR(50) NOT NULL,
    account VARCHAR(200) NOT NULL,
    paymode VARCHAR(50) NOT NULL,
    filling_station VARCHAR(200) NOT NULL,
    slip_no VARCHAR(50) NOT NULL,
    slip_date DATE NOT NULL,
    qty DECIMAL(10, 3) NOT NULL,
    rate DECIMAL(10, 2) NOT NULL,
    amount DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on doc_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_vehicle_hire_doc_id ON vehicle_hire(doc_id);

-- Add comment to table
COMMENT ON TABLE vehicle_hire IS 'Stores vehicle hire information for consignments';
