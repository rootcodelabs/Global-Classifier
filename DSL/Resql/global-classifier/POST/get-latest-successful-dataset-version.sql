SELECT id
FROM public.dataset_versions
WHERE generation_status = 'Generation_Success'
  AND id < :datasetId
ORDER BY id DESC
LIMIT 1;
