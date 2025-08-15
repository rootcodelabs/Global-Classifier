-- liquibase formatted sql

-- changeset Global-Classifier:v20-add-model-id-to-inference-logs
-- comment: Add model_id column to inference_logs table and inference_time_seconds column

ALTER TABLE public.inference_logs ADD COLUMN IF NOT EXISTS model_id VARCHAR(255);
ALTER TABLE public.inference_logs ADD COLUMN IF NOT EXISTS inference_time_seconds INTEGER;

CREATE INDEX IF NOT EXISTS idx_inference_logs_model_id ON public.inference_logs(model_id);
CREATE INDEX IF NOT EXISTS idx_inference_logs_inference_time ON public.inference_logs(inference_time_seconds);

-- rollback: ALTER TABLE public.inference_logs DROP COLUMN IF EXISTS model_id; ALTER TABLE public.inference_logs DROP COLUMN IF EXISTS inference_time_seconds;
