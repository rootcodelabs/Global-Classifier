SELECT COUNT(chunk_id)
FROM public.dataset_metadata
WHERE dataset_id = :id;