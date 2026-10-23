-- liquibase formatted sql

-- changeset Ruwini Rathnamalala:global-classifier-drop-mock-centops-ckb
-- Agency data now comes from CentOps, so the CentOps and CKB mock tables are no longer used
DROP TABLE IF EXISTS public.mock_centops;
DROP TABLE IF EXISTS public.mock_ckb;
-- rollback CREATE TABLE public.mock_centops (id SERIAL PRIMARY KEY, agency_id VARCHAR(255) NOT NULL, agency_name VARCHAR(255) NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT NOW()); CREATE TABLE public.mock_ckb (agency_id VARCHAR(50) PRIMARY KEY, agency_data_hash VARCHAR(255) NOT NULL, data_url TEXT NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT NOW());
