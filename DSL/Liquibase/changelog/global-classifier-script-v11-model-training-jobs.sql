-- liquibase formatted sql

-- changeset charith:global-classifier-model-training-jobs-enum
-- Create training job status enum
CREATE TYPE training_job_status AS ENUM ('queued', 'training-in-progress', 'trained');

-- changeset charith:global-classifier-model-training-jobs-table
CREATE TABLE public.model_training_jobs (
    job_id BIGSERIAL PRIMARY KEY,
    created_at INTEGER NOT NULL,
    model_id BIGINT NOT NULL,
    job_status training_job_status NOT NULL DEFAULT 'queued',
    model_name VARCHAR(255) NOT NULL,
    major_version INTEGER NOT NULL,
    minor_version INTEGER NOT NULL,
    latest BOOLEAN DEFAULT false,
    
    -- Add foreign key constraint to data_models table
    CONSTRAINT fk_model_training_jobs_model_id 
        FOREIGN KEY (model_id) 
        REFERENCES public.data_models(model_id) 
        ON DELETE CASCADE
);

-- changeset charith:global-classifier-model-training-jobs-indexes
-- Create indexes separately
CREATE INDEX idx_model_training_jobs_model_id ON public.model_training_jobs (model_id);
CREATE INDEX idx_model_training_jobs_status ON public.model_training_jobs (job_status);
CREATE INDEX idx_model_training_jobs_created_at ON public.model_training_jobs (created_at);