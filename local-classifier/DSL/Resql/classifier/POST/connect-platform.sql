UPDATE integration_status
SET subscription_id = :id , is_connect = TRUE
WHERE platform =:platform::platform;