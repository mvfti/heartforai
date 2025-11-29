import subprocess
import sys

if __name__ == "__main__":
    try:
        process = subprocess.Popen(["chainlit", "run", "app.py", "--watch"])
        process.wait()
    except KeyboardInterrupt:
        process.terminate()
    finally:
        sys.exit(0)
