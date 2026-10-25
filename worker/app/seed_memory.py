"""Loads the fake past postmortems in memory-seed/ into Supermemory.

Run once on the demo PC: docker compose run --rm memory-seed
Safe to re-run: each file has a fixed customId, so it updates instead of duplicating.
"""

import logging
import sys
from pathlib import Path

import httpx

from app.config import Settings
from app.log import configure_logging

log = logging.getLogger(__name__)


def main() -> int:
    settings = Settings()
    configure_logging(settings.log_level)
    if not settings.supermemory_api_key:
        log.error("SUPERMEMORY_API_KEY is empty: set it in .env first")
        return 1

    files = sorted(Path(settings.seed_dir).glob("*.md"))
    if not files:
        log.error("no .md files found", extra={"seed_dir": settings.seed_dir})
        return 1

    with httpx.Client(
        base_url=settings.supermemory_base_url,
        timeout=30,
        headers={"Authorization": f"Bearer {settings.supermemory_api_key}"},
    ) as http:
        for path in files:
            content = path.read_text(encoding="utf-8")
            title = content.splitlines()[0].lstrip("# ").strip()
            resp = http.post(
                "/v3/documents",
                json={
                    "content": content,
                    "containerTag": settings.supermemory_container_tag,
                    "customId": f"seed-{path.stem}",
                    "metadata": {"title": title, "source": "memory-seed"},
                },
            )
            if not resp.is_success:
                log.error(
                    "seed failed",
                    extra={"file": path.name, "status": resp.status_code, "body": resp.text[:300]},
                )
                return 1
            log.info("seeded", extra={"file": path.name, "title": title, **resp.json()})
    log.info("done: Supermemory indexes documents in the background, allow a minute or two")
    return 0


if __name__ == "__main__":
    sys.exit(main())
