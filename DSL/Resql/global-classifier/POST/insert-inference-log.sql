INSERT INTO public.inference_logs (
    chat_id,
    author_id,
    url,
    parsed_output
) VALUES (
    :chatId,
    :authorId,
    :url,
    :parsedOutput::jsonb
) RETURNING inference_id, chat_id, author_id, url, parsed_output, created_timestamp;
