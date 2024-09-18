# Lookback Variable

## Error fix
Students who compeleted tests while pi was down were not receiving permissions. Fixed by adding a parameter to sync_config.toml called lookback_time to look n days back. 

Default value of 7 days
