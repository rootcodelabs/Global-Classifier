DELETE FROM public.datasets
WHERE item_id = ANY(:itemIds)
RETURNING *;