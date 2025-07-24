DELETE FROM dataset_progress_sessions
WHERE process_complete = true
RETURNING id;
