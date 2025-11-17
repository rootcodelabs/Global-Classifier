SELECT id, major, minor
FROM public.dataset_versions
WHERE generation_status = 'Generation_Success'
ORDER BY id;