SELECT is_connect, subscription_id
FROM integration_status
WHERE platform=:platform::platform;