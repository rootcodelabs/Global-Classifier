WITH parsed_ids AS (
    SELECT unnest(string_to_array(:agencyIds, ' ')) AS agency_id
)
SELECT 
    mock_ckb.agency_id,
    ia.agency_name,
    mock_ckb.agency_data_hash,
    mock_ckb.data_url
FROM 
    public.mock_ckb
JOIN
    parsed_ids ON mock_ckb.agency_id = parsed_ids.agency_id
JOIN
    public.integrated_agencies ia ON mock_ckb.agency_id = ia.agency_id
WHERE 
    mock_ckb.agency_data_hash IS NOT NULL
    AND mock_ckb.data_url IS NOT NULL;