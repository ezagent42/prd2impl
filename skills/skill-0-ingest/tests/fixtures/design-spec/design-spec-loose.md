# Quick Hotfix — Fix Session Cookie Max-Age

## 5. File Changes

### Modified files
- `src/middleware/session.py` — bump cookie max-age from 3600 to 86400

## 6. Tests

Verify cookie header in browser devtools; no automated test needed for 1-line change.
