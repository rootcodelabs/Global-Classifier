INSERT INTO public.testing_inference_logs (
    model_id,
    message,
    inference_time_ms,
    parsed_output
) VALUES (
    :modelId,
    :message,
    :inferenceTimeMs,
    :parsedOutput::jsonb
) RETURNING log_id, model_id, message, inference_time_ms, parsed_output, created_timestamp;
