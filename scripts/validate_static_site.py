"""Validate that deployed TeleCLI marketing URLs are reachable and current."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ValidationConfig:
    urls: tuple[str, ...]
    expected_text: str
    attempts: int
    delay_seconds: float


def configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    )


def load_config() -> ValidationConfig:
    raw_urls = [
        os.getenv("DEPLOYMENT_URL", ""),
        os.getenv("ALIAS_URL", ""),
        os.getenv("CUSTOM_URL", ""),
    ]
    urls = tuple(dict.fromkeys(url.strip() for url in raw_urls if url.strip()))
    expected_text = os.getenv("EXPECTED_TEXT", "Secure command-line access").strip()
    attempts = int(os.getenv("VALIDATION_ATTEMPTS", "36"))
    delay_seconds = float(os.getenv("VALIDATION_DELAY_SECONDS", "10"))

    if not urls:
        logger.error("No URLs provided for deployment validation")
        raise SystemExit("No URLs provided for deployment validation")
    if not expected_text:
        logger.error("EXPECTED_TEXT cannot be empty")
        raise SystemExit("EXPECTED_TEXT cannot be empty")

    return ValidationConfig(
        urls=urls,
        expected_text=expected_text,
        attempts=attempts,
        delay_seconds=delay_seconds,
    )


def fetch_text(url: str) -> tuple[int, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "telecli-deployment-validator/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, body
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body
    except URLError as exc:
        logger.info("Fetch failed for %s: %s", url, exc.reason)
        return 0, ""


def validate_url(config: ValidationConfig, url: str) -> bool:
    for attempt in range(1, config.attempts + 1):
        status, body = fetch_text(url)
        if status == 200 and config.expected_text in body and "TeleCLI" in body:
            logger.info("Validated %s", url)
            return True

        logger.info(
            "Waiting for %s to become active (attempt %s/%s, status=%s)",
            url,
            attempt,
            config.attempts,
            status or "unreachable",
        )
        if attempt < config.attempts:
            time.sleep(config.delay_seconds)

    logger.error("Deployment validation failed for %s", url)
    return False


def run() -> None:
    configure_logging()
    config = load_config()
    failures = [url for url in config.urls if not validate_url(config, url)]
    if failures:
        raise SystemExit(1)

    logger.info("All TeleCLI deployment URLs are active")


if __name__ == "__main__":
    run()
