-- liquibase formatted sql

-- changeset Global-Classifier:v18-testing-inference-logs
-- comment: Create testing_inference_logs table for test model performance tracking

CREATE TABLE IF NOT EXISTS public.testing_inference_logs (
    log_id BIGSERIAL PRIMARY KEY,
    model_id VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    inference_time_seconds INTEGER NOT NULL,
    parsed_output JSONB NOT NULL,
    created_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_testing_inference_logs_model_id ON public.testing_inference_logs(model_id);
CREATE INDEX IF NOT EXISTS idx_testing_inference_logs_created_timestamp ON public.testing_inference_logs(created_timestamp);
CREATE INDEX IF NOT EXISTS idx_testing_inference_logs_inference_time ON public.testing_inference_logs(inference_time_seconds);

-- rollback: DROP TABLE IF EXISTS public.testing_inference_logs;
