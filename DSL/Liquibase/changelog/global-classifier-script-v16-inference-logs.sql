-- liquibase formatted sql

-- changeset thiru.dinesh:global-classifier-inference-logs-table
CREATE TABLE public.inference_logs (
    inference_id BIGSERIAL PRIMARY KEY,
    chat_id VARCHAR(255) NOT NULL,
    author_id VARCHAR(255) NOT NULL,
    url VARCHAR(2048),
    parsed_output JSONB NOT NULL,
    created_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

