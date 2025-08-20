-- liquibase formatted sql

-- changeset yourname:create-dataset-index-table
CREATE TABLE public.dataset_metadata (
    id BIGSERIAL PRIMARY KEY,
    dataset_id VARCHAR(255) NOT NULL,
    chunk_id VARCHAR(255) NOT NULL,
    included_agencies JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Optionally, you can add an index for faster JSONB querying:
CREATE INDEX idx_dataset_index_included_agencies ON public.dataset_metadata USING GIN (included_agencies);
-- CREATE INDEX idx_dataset_index_row_ids ON public.dataset_index USING GIN (row_ids);