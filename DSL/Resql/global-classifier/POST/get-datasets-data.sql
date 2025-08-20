SELECT
    item_id,
    agency_name,
    agency_id,
    data_item,
    dataset_version_id,
    CEIL(COUNT(*) OVER() / :page_size::DECIMAL) AS total_pages
FROM
    public.datasets
WHERE
    dataset_version_id = :dataset_version_id
    AND (:client_id = 'all' OR agency_id = :client_id)
ORDER BY
    item_id DESC
OFFSET ((GREATEST(:page, 1) - 1) * :page_size) LIMIT :page_size;