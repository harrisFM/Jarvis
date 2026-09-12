Permission rules live in `jarvis/policy/permissions.py` (`default_rules()`); this folder documents the
household policy in prose. Roles: guest < child < adult < owner.

| Tool | guest | child | adult | owner |
|---|---|---|---|---|
| reads (time, states, lists, recall) | allow | allow | allow | allow |
| timers, todos | allow | allow | allow | allow |
| remember | deny | allow | allow | allow |
| forget_memory | ask | ask | ask | ask |
| ha_call_service (lights, media, climate…) | ask | allow | allow | allow |
| ha_call_service on lock / alarm / cover / heater | deny | deny | ask | ask |
| send_message | deny | deny | ask | ask |
| unknown tool | ask | ask | ask | ask |
