import logging

from dimcause.core.state import get_active_session, get_all_recent_sessions, get_last_session

# Setup logging
logging.basicConfig(level=logging.INFO)

print("--- Active Session (Open) ---")
active = get_active_session()
print(f"Active: {active}")

print("\n--- Last Session (Any) ---")
last = get_last_session()
print(f"Last: {last}")

print("\n--- All Recent Sessions ---")
all_sessions = get_all_recent_sessions()
for s in all_sessions:
    print(f"  {s.date_path.name}/{s.seq} (Start: {s.start_time}) EndExists: {s.end_file.exists()}")
