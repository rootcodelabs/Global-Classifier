UPDATE public.datasets
SET
    agency_name = :agencyName,
    agency_id = :agencyId,
    data_item = :dataItem
WHERE
    item_id = :itemId
RETURNING *;