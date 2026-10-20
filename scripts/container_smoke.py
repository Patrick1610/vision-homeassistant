"""Real container HTTP + private volume + restart persistence. No external HA or AI."""

import json
import subprocess
import sys
import time
import uuid


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True, stderr=subprocess.STDOUT).strip()


def http_json(name, path):
    return json.loads(
        docker(
            "exec",
            name,
            "python",
            "-c",
            "import urllib.request;print(urllib.request.urlopen("
            + repr("http://127.0.0.1:8099" + path)
            + ",timeout=5).read().decode())",
        )
    )


def wait_ready(name):
    for attempt in range(30):
        try:
            health = http_json(name, "/api/health")
            if health.get("read_only") is True and health.get("storage") == "ready":
                return
        except subprocess.CalledProcessError:
            pass
        if attempt < 29:
            time.sleep(1)
    raise RuntimeError("Container did not become ready within 30 attempts")


def main():
    image = sys.argv[1] if len(sys.argv) > 1 else "vision:0.2.0"
    name = "vision-smoke-" + uuid.uuid4().hex[:10]
    volume = name + "-data"
    docker("volume", "create", volume)
    try:
        docker(
            "run", "-d", "--name", name, "-e", "VISION_DATA=/data", "-v", volume + ":/data", image
        )
        wait_ready(name)
        docker(
            "exec",
            name,
            "python",
            "-c",
            "import sqlite3;db=sqlite3.connect('/data/vision.db');"
            "db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',"
            "('smoke_persistence','true'));"
            "db.execute('INSERT OR REPLACE INTO exceptions VALUES (?,?,NULL)',"
            "('sensor.synthetic_smoke','Synthetic restart test'));db.commit()",
        )
        docker("restart", name)
        wait_ready(name)
        # The restarted application must itself load the persisted database.
        assert any(
            row["entity_id"] == "sensor.synthetic_smoke"
            for row in http_json(name, "/api/exceptions")
        )
        # A direct DB read proves volume persistence independently of the app cache.
        proof = docker(
            "exec",
            name,
            "python",
            "-c",
            "import sqlite3;db=sqlite3.connect('/data/vision.db');"
            "print(db.execute(\"SELECT value FROM meta WHERE key='smoke_persistence'\")"
            ".fetchone()[0])",
        )
        assert proof == "true"
        print("PASS: HTTP before/after restart, read-only status and app-loaded persistence")
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)
        subprocess.run(["docker", "volume", "rm", volume], capture_output=True, check=False)


if __name__ == "__main__":
    main()
