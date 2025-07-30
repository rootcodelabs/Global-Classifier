SELECT COUNT(*) as total_count
FROM datasets
WHERE dataset_version_id = :datasetVersionId;