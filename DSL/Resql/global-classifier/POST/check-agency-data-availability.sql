WITH parsed_ids AS (
    SELECT unnest(string_to_array(:agencyIds, ' ')) AS agency_id
)
SELECT
    p.agency_id,
    CASE WHEN c.data_url IS NOT NULL THEN true ELSE false END AS is_data_available
FROM
    parsed_ids p
LEFT JOIN
    public.mock_ckb c ON p.agency_id = c.agency_id;