-- liquibase formatted sql

-- changeset Imesh:global-classifier-base-models-multilingual-e5-large-instruct
-- Model key of the embedding classifier (src/embedding-classifier), built as an index instead of trained.
-- PostgreSQL can't drop an enum value; an unused one is harmless.
ALTER TYPE base_models ADD VALUE IF NOT EXISTS 'multilingual-e5-large-instruct';
-- rollback SELECT 1;

-- changeset Imesh:global-classifier-model-configurations-multilingual-e5-large-instruct
-- Offer it among the GUI's base models: the single model_configurations row seeded in v9.
-- (@> rather than ?, which JDBC would take for a parameter)
UPDATE model_configurations
SET base_models = base_models || '["multilingual-e5-large-instruct"]'::JSONB
WHERE NOT base_models @> '["multilingual-e5-large-instruct"]'::JSONB;
-- rollback UPDATE model_configurations SET base_models = base_models - 'multilingual-e5-large-instruct';
