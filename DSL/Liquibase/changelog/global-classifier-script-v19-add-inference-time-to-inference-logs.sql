-- liquibase formatted sql

-- changeset Global-Classifier:v19-add-inference-time-to-inference-logs
-- comment: Add inference_time_seconds column to inference_logs table for performance tracking

ALTER TABLE public.inference_logs ADD COLUMN IF NOT EXISTS inference_time_seconds INTEGER;

CREATE INDEX IF NOT EXISTS idx_inference_logs_inference_time ON public.inference_logs(inference_time_seconds);

-- rollback: ALTER TABLE public.inference_logs DROP COLUMN IF EXISTS inference_time_seconds;
