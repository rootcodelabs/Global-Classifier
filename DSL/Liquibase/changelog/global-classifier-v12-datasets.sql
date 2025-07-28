-- Liquibase changeset for creating the datasets table
-- changeset erangiar:datasets-table
CREATE TABLE public.dataset_versions (
    id BIGSERIAL PRIMARY KEY,
    major INTEGER NOT NULL,
    minor INTEGER NOT NULL,
    generation_status VARCHAR(64) NOT NULL,
    last_model_trained VARCHAR(255),
    connected_models JSONB,
    last_trained TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE public.datasets (
    item_id VARCHAR(64) PRIMARY KEY,
    agency_name VARCHAR(255),
    agency_id VARCHAR(255) NOT NULL,
    data_item VARCHAR(400) NOT NULL,
    dataset_version_id INTEGER NOT NULL
);