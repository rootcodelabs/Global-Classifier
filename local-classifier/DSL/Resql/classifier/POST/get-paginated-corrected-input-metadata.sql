SELECT  id AS inference_id,
        input_id,
        inference_time_stamp,
        inference_text,
        jsonb_pretty(predicted_labels) AS predicted_labels,
        jsonb_pretty(corrected_labels) AS corrected_labels,
        average_predicted_classes_probability,
        average_corrected_classes_probability,
        platform,
        CEIL(COUNT(*) OVER() / :page_size::DECIMAL) AS total_pages
FROM "input"
WHERE
        (is_corrected = true)
        AND (:platform = 'all' OR platform = :platform::platform)
ORDER BY
    CASE WHEN :sorting = 'asc' THEN inference_time_stamp END ASC,
    CASE WHEN :sorting = 'desc' THEN inference_time_stamp END DESC
OFFSET ((GREATEST(:page, 1) - 1) * :page_size) LIMIT :page_size;
