from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

start = time.time()
import desktop_app.main  # noqa: F401
print(f"IMPORT_SECONDS={time.time() - start:.2f}")
