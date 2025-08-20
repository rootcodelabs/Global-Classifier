UPDATE public.dataset_versions
SET generation_status = :generationStatus
WHERE id = :datasetId::bigint;