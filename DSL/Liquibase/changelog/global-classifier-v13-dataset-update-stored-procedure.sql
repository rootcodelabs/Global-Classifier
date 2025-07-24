CREATE OR REPLACE FUNCTION import_csv_dynamic(file_path TEXT)
RETURNS void AS $$
BEGIN
    EXECUTE format(
        'COPY public.datasets FROM %L WITH (FORMAT CSV, HEADER TRUE, DELIMITER '','', ENCODING ''UTF8'')',
        file_path
    );
END;
$$ LANGUAGE plpgsql;