import asyncio
import subprocess
import sys

def run_bots():
    admin = subprocess.Popen([sys.executable, "admin_bot.py"])
    user = subprocess.Popen([sys.executable, "user_bot.py"])
    admin.wait()
    user.wait()

if __name__ == "__main__":
    run_bots()
