SELECT
    (
        EXISTS (
            SELECT 1
            FROM public.dataset_versions
            WHERE generation_status = 'Generation_in_Progress'
        )
        OR EXISTS (
            SELECT 1
            FROM public.agency_data_requests
            WHERE status = 'IN_PROGRESS'
        )
    ) AS in_progress,
    (
        SELECT id
        FROM public.dataset_versions
        WHERE generation_status = 'Generation_in_Progress'
        ORDER BY id DESC
        LIMIT 1
    ) AS dataset_id;
