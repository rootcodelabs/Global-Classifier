DELETE FROM model_progress_sessions
WHERE process_complete = true
RETURNING id;
