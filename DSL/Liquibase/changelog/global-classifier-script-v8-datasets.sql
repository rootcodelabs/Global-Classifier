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
    item_id BIGSERIAL PRIMARY KEY,
    data_item VARCHAR(64) NOT NULL,
    agency VARCHAR(255),
    dataset_version_id INTEGER NOT NULL,
);
