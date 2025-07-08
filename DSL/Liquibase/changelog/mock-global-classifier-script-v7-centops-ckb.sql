
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

INSERT INTO public.mock_centops (agency_id, agency_name, created_at) VALUES
    ('1', 'ID.ee', NOW()),
    ('2', 'Politsei-_ja_Piirivalveamet', NOW());

INSERT INTO public.mock_ckb (agency_id, agency_data_hash, data_url, created_at) VALUES
    ('1', 'id_hash', 'http://minio:9000/ckb/agencies/ID.ee/ID.zip?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20250704%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20250704T044232Z&X-Amz-Expires=86400&X-Amz-SignedHeaders=host&X-Amz-Signature=58fbc63dba44a5fc0a55cad67b24665bf22a9bf20ebd98484e5ca9895db76c24', NOW()),
    ('2', 'Politsei_hash', 'http://minio:9000/ckb/agencies/Politsei-_ja_Piirivalveamet/Politsei-_ja_Piirivalveamet.zip?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20250704%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20250704T044232Z&X-Amz-Expires=86400&X-Amz-SignedHeaders=host&X-Amz-Signature=ab69f524ae6a0ba1e64ccaba0b355b4944f6216117d589e6f987b3f4679b0e06', NOW());

