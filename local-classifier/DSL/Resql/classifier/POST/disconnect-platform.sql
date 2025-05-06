UPDATE integration_status
SET subscription_id = NULL, is_connect = FALSE
WHERE platform =:platform::platform;