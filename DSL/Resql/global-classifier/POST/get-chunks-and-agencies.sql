SELECT chunk_id, included_agencies
FROM public.dataset_metadata
WHERE dataset_id = :datasetId
ORDER BY chunk_id::int