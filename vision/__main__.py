import os

import uvicorn

if __name__ == "__main__":
    # Do not trust forwarded IP headers: Ingress authorization uses the TCP peer.
    os.umask(0o077)
    uvicorn.run(
        "vision.app:create_app",
        factory=True,
        port=8099,
        host="0.0.0.0" if os.environ.get("SUPERVISOR_TOKEN") else "127.0.0.1",
        proxy_headers=False,
        access_log=False,
        log_level="warning",
    )
