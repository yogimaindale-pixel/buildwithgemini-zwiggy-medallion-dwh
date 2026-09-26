-- Gold Layer Functions

-- Helper: Date key generator (YYYYMMDD integer)
CREATE OR REPLACE FUNCTION gold.to_date_sk(ts TIMESTAMPTZ)
RETURNS INT AS $$
BEGIN
    IF ts IS NULL THEN
        RETURN -1;
    END IF;
    RETURN TO_CHAR(ts, 'YYYYMMDD')::INT;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Helper: Time key generator (HH24MI integer)
CREATE OR REPLACE FUNCTION gold.to_time_sk(ts TIMESTAMPTZ)
RETURNS INT AS $$
BEGIN
    IF ts IS NULL THEN
        RETURN -1;
    END IF;
    RETURN TO_CHAR(ts, 'HH24MI')::INT;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
