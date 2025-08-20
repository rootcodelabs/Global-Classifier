-- liquibase formatted sql

-- changeset Global-Classifier:v21-rename-inference-time-to-milliseconds
-- comment: Rename inference_time_seconds to inference_time_ms to reflect millisecond precision

-- Update inference_logs table
ALTER TABLE public.inference_logs RENAME COLUMN inference_time_seconds TO inference_time_ms;

-- Update testing_inference_logs table  
ALTER TABLE public.testing_inference_logs RENAME COLUMN inference_time_seconds TO inference_time_ms;

-- Drop old indexes
DROP INDEX IF EXISTS idx_inference_logs_inference_time;
DROP INDEX IF EXISTS idx_testing_inference_logs_inference_time;

-- Create new indexes with correct names
CREATE INDEX IF NOT EXISTS idx_inference_logs_inference_time_ms ON public.inference_logs(inference_time_ms);
CREATE INDEX IF NOT EXISTS idx_testing_inference_logs_inference_time_ms ON public.testing_inference_logs(inference_time_ms);

-- rollback: ALTER TABLE public.inference_logs RENAME COLUMN inference_time_ms TO inference_time_seconds; ALTER TABLE public.testing_inference_logs RENAME COLUMN inference_time_ms TO inference_time_seconds;
