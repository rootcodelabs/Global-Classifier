DELETE FROM stop_words
WHERE stop_word = ANY (ARRAY[:stop_words]);