"""Ensure Cloudflare Pages projects, custom domains, and DNS records exist.

Configuration is read from environment variables so secrets never need to be
stored in source control.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional local convenience only
    load_dotenv = None

logger = logging.getLogger(__name__)
API_BASE = "https://api.cloudflare.com/client/v4"


class CloudflareAPIError(RuntimeError):
    """Raised when the Cloudflare API returns an unsuccessful response."""


@dataclass(frozen=True)
class Config:
    api_token: str
    account_id: str
    project_name: str
    production_branch: str
    custom_domains: tuple[str, ...]
    dns_target: str
    zone_name: str
    replace_conflicting_dns: bool


def configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    )


def load_config() -> Config:
    if load_dotenv is not None:
        load_dotenv()

    api_token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    project_name = os.getenv("CLOUDFLARE_PAGES_PROJECT", "telecli").strip()
    production_branch = os.getenv("CLOUDFLARE_PAGES_PRODUCTION_BRANCH", "main").strip()
    custom_domains = tuple(
        domain.strip().lower()
        for domain in os.getenv("CLOUDFLARE_PAGES_CUSTOM_DOMAINS", "telecli.org,www.telecli.org").split(",")
        if domain.strip()
    )
    dns_target = os.getenv("CLOUDFLARE_DNS_TARGET", f"{project_name}.pages.dev").strip().lower()
    zone_name = os.getenv("CLOUDFLARE_ZONE_NAME", infer_zone_name(custom_domains)).strip().lower()
    replace_conflicting_dns = os.getenv("CLOUDFLARE_REPLACE_CONFLICTING_DNS", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    missing: list[str] = []
    if not api_token:
        missing.append("CLOUDFLARE_API_TOKEN")
    if not account_id:
        missing.append("CLOUDFLARE_ACCOUNT_ID")
    if not project_name:
        missing.append("CLOUDFLARE_PAGES_PROJECT")
    if not production_branch:
        missing.append("CLOUDFLARE_PAGES_PRODUCTION_BRANCH")
    if not custom_domains:
        missing.append("CLOUDFLARE_PAGES_CUSTOM_DOMAINS")
    if not zone_name:
        missing.append("CLOUDFLARE_ZONE_NAME")

    if missing:
        message = f"Missing required Cloudflare configuration: {', '.join(missing)}"
        logger.error(message)
        raise SystemExit(message)

    return Config(
        api_token=api_token,
        account_id=account_id,
        project_name=project_name,
        production_branch=production_branch,
        custom_domains=custom_domains,
        dns_target=dns_target,
        zone_name=zone_name,
        replace_conflicting_dns=replace_conflicting_dns,
    )


def infer_zone_name(custom_domains: tuple[str, ...]) -> str:
    if not custom_domains:
        return "telecli.org"
    labels = custom_domains[0].split(".")
    return ".".join(labels[-2:]) if len(labels) >= 2 else custom_domains[0]


def api_request(config: Config, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"{API_BASE}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {config.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "telecli-pages-deploy/1.0",
        },
    )

    try:
        with urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        try:
            data = cast(dict[str, Any], json.loads(error_body))
        except json.JSONDecodeError:
            data: dict[str, Any] = {"success": False, "errors": [{"message": str(error_body or exc.reason)}]}
        data["_http_status"] = exc.code
        return data

    return data


def ensure_success(data: dict[str, Any], action: str, allowed_statuses: set[int] | None = None) -> dict[str, Any]:
    status = data.get("_http_status")
    if allowed_statuses and status in allowed_statuses:
        return data
    if data.get("success", False):
        return data

    errors = cast(list[Any], data.get("errors") or [])
    messages = "; ".join(format_cloudflare_error(error) for error in errors) or "unknown error"
    logger.error("Cloudflare API failed during %s: %s", action, messages)
    raise CloudflareAPIError(f"Cloudflare API failed during {action}: {messages}")


def format_cloudflare_error(error: Any) -> str:
    if isinstance(error, Mapping):
        mapped_error = cast(Mapping[str, Any], error)
        message = mapped_error.get("message")
        return str(message) if message is not None else "unknown error"
    return str(error)


def quoted(value: str) -> str:
    return quote(value, safe="")


def get_project(config: Config) -> dict[str, Any] | None:
    data = api_request(
        config,
        "GET",
        f"/accounts/{quoted(config.account_id)}/pages/projects/{quoted(config.project_name)}",
    )
    if data.get("_http_status") == 404:
        return None
    return ensure_success(data, "get Pages project")["result"]


def ensure_project(config: Config) -> None:
    project = get_project(config)
    if project is None:
        logger.info("Creating Cloudflare Pages project %s", config.project_name)
        data = api_request(
            config,
            "POST",
            f"/accounts/{quoted(config.account_id)}/pages/projects",
            {
                "name": config.project_name,
                "production_branch": config.production_branch,
            },
        )
        ensure_success(data, "create Pages project")
    else:
        logger.info("Cloudflare Pages project %s already exists", config.project_name)

    logger.info("Ensuring production branch for %s is %s", config.project_name, config.production_branch)
    data = api_request(
        config,
        "PATCH",
        f"/accounts/{quoted(config.account_id)}/pages/projects/{quoted(config.project_name)}",
        {"production_branch": config.production_branch},
    )
    ensure_success(data, "update Pages production branch")


def get_zone_id(config: Config) -> str:
    query = urlencode({"name": config.zone_name})
    data = api_request(config, "GET", f"/zones?{query}")
    result = cast(list[dict[str, Any]], ensure_success(data, "list zones").get("result") or [])
    if not result:
        message = f"Cloudflare zone not found for {config.zone_name}"
        logger.error(message)
        raise CloudflareAPIError(message)

    zone_id = str(result[0]["id"])
    logger.info("Using Cloudflare zone %s", config.zone_name)
    return zone_id


def list_dns_records(config: Config, zone_id: str, record_name: str) -> list[dict[str, Any]]:
    query = urlencode({"name": record_name})
    data = api_request(config, "GET", f"/zones/{quoted(zone_id)}/dns_records?{query}")
    return ensure_success(data, f"list DNS records for {record_name}").get("result") or []


def dns_record_payload(record_name: str, dns_target: str) -> dict[str, Any]:
    return {
        "type": "CNAME",
        "name": record_name,
        "content": dns_target,
        "ttl": 1,
        "proxied": True,
        "comment": "Managed by TeleCLI GitHub Actions deployment",
    }


def ensure_dns_record(config: Config, zone_id: str, record_name: str) -> None:
    records = list_dns_records(config, zone_id, record_name)
    cname_records = [record for record in records if record.get("type") == "CNAME"]
    desired = dns_record_payload(record_name, config.dns_target)

    for record in cname_records:
        if record.get("content", "").rstrip(".").lower() == config.dns_target.rstrip(".").lower() and record.get("proxied"):
            logger.info("DNS record %s already points to %s", record_name, config.dns_target)
            return

    conflicting_records = [record for record in records if record.get("type") in {"A", "AAAA", "CNAME"}]
    if conflicting_records and not config.replace_conflicting_dns:
        message = (
            f"Conflicting DNS records exist for {record_name}. Set "
            "CLOUDFLARE_REPLACE_CONFLICTING_DNS=true to replace A/AAAA/CNAME records."
        )
        logger.error(message)
        raise CloudflareAPIError(message)

    for record in conflicting_records:
        logger.info("Removing conflicting %s DNS record for %s", record.get("type"), record_name)
        data = api_request(config, "DELETE", f"/zones/{quoted(zone_id)}/dns_records/{quoted(record['id'])}")
        ensure_success(data, f"delete conflicting DNS record for {record_name}")

    logger.info("Creating DNS CNAME %s -> %s", record_name, config.dns_target)
    data = api_request(config, "POST", f"/zones/{quoted(zone_id)}/dns_records", desired)
    ensure_success(data, f"create DNS record for {record_name}")


def list_pages_domains(config: Config) -> list[dict[str, Any]]:
    data = api_request(
        config,
        "GET",
        f"/accounts/{quoted(config.account_id)}/pages/projects/{quoted(config.project_name)}/domains",
    )
    return ensure_success(data, "list Pages custom domains").get("result") or []


def ensure_pages_domain(config: Config, domain_name: str) -> None:
    existing_domains = {domain.get("name", "").lower(): domain for domain in list_pages_domains(config)}
    if domain_name in existing_domains:
        status = existing_domains[domain_name].get("status", "unknown")
        logger.info("Pages custom domain %s already exists with status %s", domain_name, status)
        return

    logger.info("Adding Pages custom domain %s to %s", domain_name, config.project_name)
    data = api_request(
        config,
        "POST",
        f"/accounts/{quoted(config.account_id)}/pages/projects/{quoted(config.project_name)}/domains",
        {"name": domain_name},
    )
    ensure_success(data, f"add Pages custom domain {domain_name}")


def run() -> None:
    configure_logging()
    config = load_config()
    logger.info("Preparing Cloudflare Pages deployment for project %s", config.project_name)

    ensure_project(config)
    zone_id = get_zone_id(config)

    for domain in config.custom_domains:
        ensure_dns_record(config, zone_id, domain)
        ensure_pages_domain(config, domain)

    logger.info("Cloudflare Pages setup completed for %s", config.project_name)


if __name__ == "__main__":
    try:
        run()
    except CloudflareAPIError as exc:
        logger.exception("Cloudflare setup failed: %s", exc)
        sys.exit(1)
