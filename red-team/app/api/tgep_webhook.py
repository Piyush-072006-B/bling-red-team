"""
TGEP Outbound Webhook — Fire patch proposals to TGEP
======================================================
After a red_team_reports entry is created with recommended_action=PATCH
and severity=HIGH or CRITICAL, fire a webhook to TGEP_WEBHOOK_URL.

Payload schema (per master prompt):
    {
        "source":                  "red_team",
        "report_id":               str (uuid),
        "event_type":              "EVASION_CONFIRMED",
        "archetype":               str,
        "gate_vulnerability":      str | None,
        "proposed_patch_summary":  str,
        "severity":                str,
        "recommended_action":      "PATCH",
        "created_at":              str (ISO 8601),
    }

Retry policy: one retry on failure (as specified in master prompt).
Never blocks Blue Team. All errors are logged and swallowed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import get_settings
from app.utils.audit_logger import get_logger

log = get_logger(__name__)

# Only fire webhook for these severities
_WEBHOOK_SEVERITY_THRESHOLD = {"HIGH", "CRITICAL"}


def _build_webhook_payload(
    report_id: str,
    archetype: str,
    gate_vulnerability: str | None,
    proposed_patch_summary: str,
    severity: str,
    recommended_action: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build the TGEP webhook payload."""
    return {
        "source": "red_team",
        "report_id": report_id,
        "event_type": "EVASION_CONFIRMED",
        "archetype": archetype,
        "gate_vulnerability": gate_vulnerability,
        "proposed_patch_summary": proposed_patch_summary,
        "severity": severity,
        "recommended_action": recommended_action,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
    }


async def fire_tgep_webhook(
    report_id: str,
    archetype: str,
    gate_vulnerability: str | None,
    proposed_patch_summary: str,
    severity: str,
    recommended_action: str = "PATCH",
    created_at: str | None = None,
) -> dict[str, Any] | None:
    """
    POST an evasion-confirmed event to the TGEP webhook endpoint.
    Only fires when severity is HIGH or CRITICAL.

    Retry policy: one retry on network/timeout failure.
    Returns parsed JSON if webhook was accepted (2xx), None otherwise.
    All failures are logged and never re-raised (non-blocking).
    """
    if severity not in _WEBHOOK_SEVERITY_THRESHOLD:
        log.debug(
            "tgep_webhook_skipped_low_severity",
            severity=severity,
            report_id=report_id,
        )
        return None

    settings = get_settings()
    webhook_url = settings.tgep_webhook_url
    payload = _build_webhook_payload(
        report_id=report_id,
        archetype=archetype,
        gate_vulnerability=gate_vulnerability,
        proposed_patch_summary=proposed_patch_summary,
        severity=severity,
        recommended_action=recommended_action,
        created_at=created_at,
    )

    log.info(
        "tgep_webhook_firing",
        url=webhook_url,
        report_id=report_id,
        severity=severity,
        archetype=archetype,
    )

    for attempt in range(1, 3):  # attempt 1, then retry (attempt 2)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    webhook_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Source": "red-team",
                    },
                )
                if resp.is_success:
                    log.info(
                        "tgep_webhook_sent",
                        report_id=report_id,
                        status_code=resp.status_code,
                        attempt=attempt,
                    )
                    return resp.json()
                else:
                    log.warning(
                        "tgep_webhook_rejected",
                        report_id=report_id,
                        status_code=resp.status_code,
                        attempt=attempt,
                        body=resp.text[:200],
                    )
                    if attempt == 2:
                        return None
                    # Fall through to retry

        except httpx.TimeoutException as exc:
            log.warning(
                "tgep_webhook_timeout",
                report_id=report_id,
                attempt=attempt,
                detail=str(exc),
            )
            if attempt == 2:
                return None

        except httpx.RequestError as exc:
            log.warning(
                "tgep_webhook_connection_error",
                report_id=report_id,
                attempt=attempt,
                detail=str(exc),
            )
            if attempt == 2:
                return None

        except Exception as exc:
            log.error(
                "tgep_webhook_unexpected_error",
                report_id=report_id,
                attempt=attempt,
                detail=str(exc),
            )
            return None

    return None


async def maybe_fire_tgep_for_report(report: dict[str, Any]) -> dict[str, Any] | None:
    """
    Convenience wrapper: fire TGEP webhook if the report warrants it.

    Args:
        report: red_team_reports row dict with fields:
                id, report_type, payload, recommended_action, severity, created_at

    Returns:
        Parsed JSON if webhook was sent successfully, None otherwise.
    """
    severity = report.get("severity") or "LOW"
    recommended_action = report.get("recommended_action", "ACCEPT")

    # Only fire for PATCH recommendations at HIGH/CRITICAL severity
    if recommended_action != "PATCH" or severity not in _WEBHOOK_SEVERITY_THRESHOLD:
        return None

    payload_data: dict = report.get("payload", {})
    archetype = payload_data.get("archetype", "UNKNOWN")
    gate_vulnerability = payload_data.get("gate_vulnerability")
    gate_list = payload_data.get("gate_vulnerabilities", [])
    if not gate_vulnerability and gate_list:
        gate_vulnerability = gate_list[0]

    # Build a human-readable patch summary
    evasion_count = payload_data.get("evasions_found", "unknown")
    proposed_patch_summary = (
        f"Red Team found {evasion_count} confirmed evasion(s) for archetype '{archetype}'. "
        f"Gate vulnerability: {gate_vulnerability or 'none identified'}. "
        f"Recommend reviewing detection thresholds for this pattern."
    )

    return await fire_tgep_webhook(
        report_id=str(report.get("id", "")),
        archetype=archetype,
        gate_vulnerability=gate_vulnerability,
        proposed_patch_summary=proposed_patch_summary,
        severity=severity,
        recommended_action=recommended_action,
        created_at=report.get("created_at"),
    )
