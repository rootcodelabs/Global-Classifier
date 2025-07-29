DELETE FROM public.datasets
WHERE item_id = ANY(ARRAY[:itemIds]::text[])
RETURNING *;