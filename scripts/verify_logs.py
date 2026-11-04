import os
import json

log_dir = "logs"
app_log = os.path.join(log_dir, "app.log")
ai_log = os.path.join(log_dir, "ai_activity.log")

print("=== LOG FILES ===")
print(f"app.log exists    : {os.path.exists(app_log)} ({os.path.getsize(app_log)} bytes)")
print(f"ai_activity.log   : {os.path.exists(ai_log)} ({os.path.getsize(ai_log)} bytes)")

print()
print("=== ai_activity.log (all lines) ===")
with open(ai_log, encoding="utf-8") as f:
    lines = [l.strip() for l in f if l.strip()]

print(f"Total JSON lines: {len(lines)}")
all_valid = True
for i, line in enumerate(lines):
    try:
        obj = json.loads(line)
        score = obj.get("score", obj.get("final_score", "-"))
        print(f"  [{i+1}] event={obj.get('event')!r:30s} | score={score}")
    except json.JSONDecodeError as e:
        print(f"  [{i+1}] INVALID JSON: {e}")
        all_valid = False

print()
print(f"All JSON valid: {all_valid}")
