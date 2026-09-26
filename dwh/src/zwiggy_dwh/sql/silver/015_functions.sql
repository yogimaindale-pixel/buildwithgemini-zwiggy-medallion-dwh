-- Silver Layer Helper Functions

-- Function: Hash PII fields using SHA256
CREATE OR REPLACE FUNCTION silver.mask_pii(val TEXT)
RETURNS TEXT AS $$
BEGIN
    IF val IS NULL OR TRIM(val) = '' THEN
        RETURN NULL;
    END IF;
    RETURN encode(digest(TRIM(LOWER(val)), 'sha256'), 'hex');
END;
$$ LANGUAGE plpgsql IMMUTABLE;
