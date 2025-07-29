DELETE FROM public.dataset_versions
WHERE id = :datasetVersionId
RETURNING *;