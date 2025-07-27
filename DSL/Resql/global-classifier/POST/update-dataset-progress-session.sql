UPDATE dataset_progress_sessions
SET
    generation_status = :generation_status::Generation_Progress_Status,
    generation_message = :generation_message,
    progress_percentage = :progress_percentage,
    process_complete = :process_complete
WHERE id = :id;