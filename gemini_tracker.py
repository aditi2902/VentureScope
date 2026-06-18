import threading

_lock = threading.Lock()
GEMINI_CALLS = 0

def track_call():
    global GEMINI_CALLS
    with _lock:
        GEMINI_CALLS += 1
        print(f"Nvidia DeepSeek Call #{GEMINI_CALLS}")
