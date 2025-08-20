INSERT INTO public.inference_logs (
    chat_id,
    url,
    model_id,
    inference_time_ms,
    parsed_output
) VALUES (
    :chatId,
    :url,
    :modelId,
    :inferenceTimeMs,
    :parsedOutput::jsonb
) RETURNING inference_id, chat_id, url, model_id, inference_time_ms, parsed_output, created_timestamp;
