
-- changeset erangi:global-classifier-centops-ckb-tables
CREATE TABLE public.mock_centops (
    id          SERIAL PRIMARY KEY,
    agency_id   VARCHAR(255) NOT NULL,
    agency_name VARCHAR(255) NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE public.mock_ckb (
    agency_id         VARCHAR(50) PRIMARY KEY,
    agency_data_hash  VARCHAR(255) NOT NULL,
    data_url          TEXT NOT NULL,
    created_at        TIMESTAMP NOT NULL DEFAULT NOW()
);

