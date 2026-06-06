"""
API Router — GET /red-team/briefing
=====================================
Returns a single human-readable JSON intelligence briefing synthesised from
the entire evasion knowledge base.  Designed to be consumed directly by a
Blue Team developer with zero context — plain English titles, exact fix
instructions, file references.

Response shape:
    {
        "generated_at":              str (ISO timestamp),
        "threat_summary":            str (e.g. "3 active evasion patterns. 1 CRITICAL, 2 HIGH."),
        "immediate_action_required": list[BriefingItem],   # CRITICAL + evasion_success=True
        "monitor":                   list[BriefingItem],   # HIGH
        "structural_findings":       list[BriefingItem],   # Structural evasion patterns identified — shadow scorer offline, severity unconfirmed. Review recommended.
        "top_exploitable_features":  list[str],            # top-3 by frequency across KB
        "context_multipliers_at_risk": list[str],          # e.g. ["festival_0.70x"]
    }

BriefingItem:
    {
        "priority":       int,
        "severity":       str,
        "title":          str,
        "what_was_found": str,
        "what_to_change": str,
        "file":           str,
        "evasion_ids":    list[str],
    }

Auth: X-API-Key (same as all other endpoints).
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends

from app.knowledge.kb_store import get_all_evasions
from app.utils.audit_logger import get_logger
from app.utils.auth import require_api_key

log = get_logger(__name__)

router = APIRouter(
    prefix="/red-team",
    tags=["briefing"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Title / fix copy generators — plain English for each mutation/bypass type
# ─────────────────────────────────────────────────────────────────────────────

_MUTATION_TITLES: dict[str, tuple[str, str, str]] = {
    # (title, what_was_found, what_to_change)
    "threshold_amount_50k": (
        "Structuring below ₹50k threshold",
        "Feature amounts were reduced to 92% of the ₹50k threshold, dropping the fraud score below the BLOCK boundary.",
        "Lower the structuring detection threshold from 50000 to 44000, or add a velocity check for amounts consistently near the threshold.",
    ),
    "threshold_amount_100k": (
        "Structuring below ₹1L threshold",
        "Feature amounts were reduced to 92% of the ₹1L threshold, evading the high-value transaction gate.",
        "Add a secondary detection rule for amounts consistently clustering just below ₹1L.",
    ),
    "threshold_amount_1m": (
        "Structuring below ₹10L threshold",
        "Feature amounts were reduced to 92% of the ₹10L PMLA reporting threshold.",
        "Implement a time-series variance check: flag accounts with amounts consistently near ₹10L across multiple transactions.",
    ),
    "timing_day": (
        "Night transaction ratio suppressed",
        "night_txn_ratio was pushed from the original value to 0.15, making the transaction appear daytime. The night-pattern gate was bypassed.",
        "Add a 7-day rolling night_txn_ratio baseline — a sudden drop from a high baseline should itself trigger a review flag.",
    ),
    "velocity_20pct": (
        "Velocity reduced 20% to evade burst gate",
        "burst_score and velocity_ratio were reduced by 20%, pushing the score below the BLOCK threshold.",
        "Tighten the velocity gate trigger threshold from the current value by 15–20% to close this gap.",
    ),
    "velocity_30pct": (
        "Velocity reduced 30% to evade burst gate",
        "burst_score and velocity_ratio were reduced by 30%, achieving a score drop below BLOCK.",
        "Consider a combined gate: velocity_ratio × burst_score > threshold, so reducing one factor alone is insufficient.",
    ),
    "velocity_40pct": (
        "Velocity reduced 40% — full burst gate bypass",
        "A 40% reduction in velocity features fully evaded detection. This indicates the burst gate has no floor.",
        "Add an absolute floor: flag any account with burst_score > 0.3 regardless of relative reduction.",
    ),
    "context_festival": (
        "Festival multiplier abused (0.70x score reduction)",
        "Setting is_festival_period=1 applied a 0.70x multiplier to the raw score, reducing it below the BLOCK threshold.",
        "Make the festival multiplier conditional: only apply when the payee account is a registered merchant VPA. Raw P2P transfers during festivals should not receive the discount.",
    ),
    "context_senior": (
        "Senior-account night exemption exploited",
        "Setting night_txn_ratio=0 exploited the senior-account night-pattern exemption, removing the night penalty entirely.",
        "Add a secondary trigger: senior accounts with night_txn_ratio suddenly dropping to zero after a history of night transactions should be flagged — the pattern change itself is a signal.",
    ),
    "novelty_zero": (
        "Counterparty novelty zeroed — bipartite gate bypass",
        "Setting counterparty_novelty=0 bypassed the bipartite gate by making all payees appear to be known counterparties.",
        "Cross-validate counterparty_novelty against the account's 90-day unique-VPA history. A zero score for a new payee VPA should be rejected.",
    ),
}

_GRAPH_TITLES: dict[str, tuple[str, str, str]] = {
    "graph_bypass_cycle": (
        "9-hop cycle path outside detection window",
        "A 9-hop A→C path was synthesised. Blue Team's cycle detector checks 2–8 hops only, so 9-hop paths are invisible.",
        "Extend the cycle detection window in graph_engine.py to 2–12 hops. Also add detection for paths with very small per-hop amount decay (< 1%).",
    ),
    "graph_bypass_sink": (
        "Sink score diluted via dispersal outflows",
        "5 small outflow transactions (15% each) immediately after the main inflow reduced retention to ~0.25, pushing sink_score below 0.6.",
        "Add a temporal sink check: accounts that receive a large inflow and then disperse >50% within 24h should trigger a REVIEW regardless of the point-in-time sink_score.",
    ),
    "graph_bypass_bipartite": (
        "Bipartite density halved by splitting sender batch",
        "7 senders were split into 4+3 batches targeting 2 recipient accounts. Combined bipartite density fell from 1.0 to 0.5, below the 0.7 trigger.",
        "Lower the bipartite density trigger threshold from 0.7 to 0.55. Also detect when the same set of senders distributes across multiple recipients within a short window.",
    ),
    "graph_bypass_cash_mule_sink": (
        "48h digital activity buffer breaks dormancy pattern",
        "3 small digital payments across 48h were inserted between the receive event and ATM withdrawal, breaking the direct receive→ATM dormancy pattern.",
        "Update the cash_mule_sink gate to check for ATM withdrawal within 72h (not just direct receive→ATM). Flag accounts with receive → small digital spends → large ATM withdrawal.",
    ),
    "graph_bypass_merchant_terminal": (
        "Round-trip split across 2 POS terminals",
        "The round-trip transaction was split across 2 distinct POS terminals, each with a separate merchant account. The single-terminal round-trip pattern was avoided.",
        "Extend merchant terminal detection to group by merchant owner, not terminal ID. A round-trip across terminals owned by the same merchant should still trigger the gate.",
    ),
}

_UNKNOWN_TITLE = (
    "Evasion pattern detected",
    "An evasion was detected but the mutation type is not in the known taxonomy.",
    "Review the evasion record manually and update the briefing taxonomy.",
)

_BLUE_TEAM_FILES: dict[str, str] = {
    "threshold_amount_50k":    "blue_team/scoring/thresholds.py",
    "threshold_amount_100k":   "blue_team/scoring/thresholds.py",
    "threshold_amount_1m":     "blue_team/scoring/thresholds.py",
    "timing_day":              "blue_team/features/temporal.py",
    "velocity_20pct":          "blue_team/scoring/velocity.py",
    "velocity_30pct":          "blue_team/scoring/velocity.py",
    "velocity_40pct":          "blue_team/scoring/velocity.py",
    "context_festival":        "blue_team/context/multipliers.py",
    "context_senior":          "blue_team/context/multipliers.py",
    "novelty_zero":            "blue_team/features/counterparty.py",
    "graph_bypass_cycle":      "blue_team/graph/cycle_detector.py",
    "graph_bypass_sink":       "blue_team/graph/sink_detector.py",
    "graph_bypass_bipartite":  "blue_team/graph/bipartite_detector.py",
    "graph_bypass_cash_mule_sink":     "blue_team/graph/cash_mule_detector.py",
    "graph_bypass_merchant_terminal":  "blue_team/graph/merchant_detector.py",
}

_CONTEXT_MULTIPLIER_LABELS: dict[str, str] = {
    "is_festival_period":   "festival_0.70x",
    "is_senior_account":    "senior_0.85x",
    "is_rural_account":     "rural_0.90x",
    "is_first_time_upi":    "first_time_upi_0.80x",
    "is_govt_salary_credit": "govt_salary_0.75x",
}

_FEATURE_INTELLIGENCE: dict[str, tuple[str, str]] = {
    "velocity_ratio": (
        "Reducing transaction velocity by 20-40% is the most common evasion technique in this archetype. Blue Team relies heavily on burst_score and velocity_ratio — an attacker slowing down slightly evades detection.",
        "Add rolling 7-day velocity baseline instead of point-in-time measurement",
    ),
    "burst_score": (
        "Reducing transaction velocity by 20-40% is the most common evasion technique in this archetype. Blue Team relies heavily on burst_score and velocity_ratio — an attacker slowing down slightly evades detection.",
        "Add rolling 7-day velocity baseline instead of point-in-time measurement",
    ),
    "amount": (
        "Structuring below ₹50K/₹1L/₹10L is used to evade threshold detection.",
        "Implement a time-series variance check: flag accounts with amounts consistently near thresholds.",
    ),
    "night_txn_ratio": (
        "Daytime disguise of night fraud shifts night_txn_ratio, bypassing the night-pattern gate.",
        "Add a 7-day rolling night_txn_ratio baseline — a sudden drop should trigger a review flag.",
    ),
    "counterparty_novelty": (
        "Pretending payee is known bypasses the bipartite gate by making all payees appear to be known counterparties.",
        "Cross-validate counterparty_novelty against the account's 90-day unique-VPA history.",
    ),
}

_MULTIPLIER_INTELLIGENCE: dict[str, tuple[float, str, str]] = {
    "is_festival_period": (
        0.70,
        "Festival period multiplier (x0.70) was tested — flagging a digital_arrest transaction as festival-period reduces its score by 30%. Attackers could time fraud during Diwali/Holi.",
        "Festival multiplier should not apply when payee_vpa_age_days < 7",
    ),
    "is_senior_account": (
        0.85,
        "Senior-account night exemption was tested — removing the night penalty entirely.",
        "Add a secondary trigger: senior accounts with night_txn_ratio suddenly dropping to zero should be flagged.",
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Core briefing logic
# ─────────────────────────────────────────────────────────────────────────────


def _get_copy(mutation_type: str | None) -> tuple[str, str, str]:
    """Return (title, what_was_found, what_to_change) for a mutation_type."""
    if not mutation_type:
        return _UNKNOWN_TITLE
    copy = _MUTATION_TITLES.get(mutation_type) or _GRAPH_TITLES.get(mutation_type)
    return copy if copy else _UNKNOWN_TITLE


def _build_briefing_item(
    priority: int,
    evasion: dict[str, Any],
) -> dict[str, Any]:
    """Build a single BriefingItem from an evasion_kb row."""
    mutation_type: str | None = evasion.get("mutation_type")
    severity: str = evasion.get("severity", "LOW")
    title, what_was_found, what_to_change = _get_copy(mutation_type)
    file_ref = _BLUE_TEAM_FILES.get(mutation_type or "", "blue_team/ (review manually)")

    return {
        "priority": priority,
        "severity": severity,
        "title": title,
        "what_was_found": what_was_found,
        "what_to_change": what_to_change,
        "file": file_ref,
        "evasion_ids": [evasion["id"]],
    }


def _merge_by_title(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Merge BriefingItems that share the same title (same root cause).
    Merged items accumulate all evasion_ids and take the lowest priority number.
    """
    seen: dict[str, dict[str, Any]] = {}
    for item in items:
        key = item["title"]
        if key not in seen:
            seen[key] = dict(item)
        else:
            seen[key]["evasion_ids"].extend(item["evasion_ids"])
    # Re-number priorities
    result = list(seen.values())
    for i, item in enumerate(result, start=1):
        item["priority"] = i
    return result


def _build_mutation_intelligence(all_evasions: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the structural intelligence layer that runs regardless of shadow scorer status."""
    feature_stats: dict[str, list[float]] = {}
    multiplier_stats: dict[str, int] = {}
    archetypes: set[str] = set()
    total_mutations = 0

    for ev in all_evasions:
        if ev.get("mutation_type"):
            total_mutations += 1

        arch = ev.get("archetype")
        if arch and arch != "UNKNOWN":
            archetypes.add(arch)

        # Features
        fs = ev.get("feature_sensitivity_result")
        if isinstance(fs, dict):
            for feat_item in fs.get("top_5_exploitable_features", []):
                feat = feat_item.get("feature")
                delta = feat_item.get("delta_value")
                if feat and delta is not None:
                    if feat not in feature_stats:
                        feature_stats[feat] = []
                    feature_stats[feat].append(float(delta))

        # Multipliers
        ctx = ev.get("context_bypass_result")
        if isinstance(ctx, dict):
            abused = ctx.get("multiplier_abused")
            if abused:
                multiplier_stats[abused] = multiplier_stats.get(abused, 0) + 1
        direct_abused = ev.get("context_multiplier_abused")
        if direct_abused:
            multiplier_stats[direct_abused] = multiplier_stats.get(direct_abused, 0) + 1

    # Format top features
    top_features_list = []
    sorted_features = sorted(feature_stats.items(), key=lambda x: len(x[1]), reverse=True)
    for feat, deltas in sorted_features:
        pe, rec = _FEATURE_INTELLIGENCE.get(feat, ("Unknown evasion technique.", "Review manually."))
        avg_delta = sum(deltas) / len(deltas) if deltas else 0.0
        top_features_list.append({
            "feature": feat,
            "times_exploited": len(deltas),
            "avg_delta": round(avg_delta, 2),
            "plain_english": pe,
            "recommendation": rec,
        })

    # Format multipliers
    multipliers_list = []
    for mult, count in multiplier_stats.items():
        val, pe, rec = _MULTIPLIER_INTELLIGENCE.get(mult, (1.0, "Unknown multiplier.", "Review manually."))
        multipliers_list.append({
            "multiplier": mult,
            "multiplier_value": val,
            "times_tested": count,
            "plain_english": pe,
            "recommendation": rec,
        })

    primary_archetype = list(archetypes)[0] if archetypes else "digital_arrest"
    
    # Check if shadow scorer was offline for all records
    scorer_offline = len(all_evasions) > 0 and all(ev.get("score_mutated") is None for ev in all_evasions)
    summary = "Shadow scorer offline — showing structural analysis only" if scorer_offline else "Structural analysis generated from mutated payloads"
    if not all_evasions:
        summary = "No evasion data available"

    return {
        "summary": summary,
        "top_exploitable_features": top_features_list[:3],
        "context_multipliers_tested": multipliers_list,
        "archetype_confirmed": primary_archetype,
        "mutations_generated": total_mutations,
        "tgep_test_suggested": True,
        "tgep_payload_hint": "Use timing_day mutation vector for TGEP testing — shifts night_txn_ratio to 0.15 while keeping all other fraud signals intact",
    }


def build_briefing() -> dict[str, Any]:
    """Build the full briefing dict from the current evasion KB state."""
    all_evasions = get_all_evasions()
    now = datetime.now(timezone.utc).isoformat()

    immediate: list[dict[str, Any]] = []
    monitor: list[dict[str, Any]] = []
    structural_findings: list[dict[str, Any]] = []
    feature_counter: Counter = Counter()
    multipliers_seen: set[str] = set()

    for ev in all_evasions:
        severity = ev.get("severity", "LOW")
        evasion_success = ev.get("evasion_success", False)

        # Bucket by severity
        item = _build_briefing_item(0, ev)   # priority set later by merge
        if severity == "CRITICAL" and evasion_success:
            immediate.append(item)
        elif severity == "HIGH":
            monitor.append(item)
        else:
            structural_findings.append(item)

        # Accumulate top exploitable features from feature_sensitivity_result
        fs = ev.get("feature_sensitivity_result")
        if isinstance(fs, dict):
            for feat_item in fs.get("top_5_exploitable_features", []):
                feat = feat_item.get("feature")
                if feat:
                    feature_counter[feat] += 1

        # Accumulate context multipliers
        ctx = ev.get("context_bypass_result")
        if isinstance(ctx, dict):
            abused = ctx.get("multiplier_abused")
            if abused and _CONTEXT_MULTIPLIER_LABELS.get(abused):
                multipliers_seen.add(_CONTEXT_MULTIPLIER_LABELS[abused])
        # Also check direct field
        direct_abused = ev.get("context_multiplier_abused")
        if direct_abused and _CONTEXT_MULTIPLIER_LABELS.get(direct_abused):
            multipliers_seen.add(_CONTEXT_MULTIPLIER_LABELS[direct_abused])

    # Merge duplicate titles and re-number
    immediate = _merge_by_title(immediate)
    monitor   = _merge_by_title(monitor)
    structural_findings = _merge_by_title(structural_findings)

    # Build threat summary
    n_critical = len(immediate)
    n_high = len(monitor)
    total_patterns = n_critical + n_high + len(structural_findings)
    threat_summary = (
        f"{total_patterns} active evasion pattern{'s' if total_patterns != 1 else ''}. "
        f"{n_critical} CRITICAL, {n_high} HIGH."
    )

    # Top exploitable features (top 3 by KB frequency)
    top_features = [feat for feat, _ in feature_counter.most_common(3)]

    log.info(
        "briefing_generated",
        total_patterns=total_patterns,
        immediate=n_critical,
        monitor=n_high,
        structural_findings=len(structural_findings),
        top_features=top_features,
    )

    return {
        "generated_at": now,
        "threat_summary": threat_summary,
        "immediate_action_required": immediate,
        "monitor": monitor,
        "structural_findings": structural_findings,
        "top_exploitable_features": top_features,
        "context_multipliers_at_risk": sorted(multipliers_seen),
        "mutation_intelligence": _build_mutation_intelligence(all_evasions),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Route
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/briefing",
    summary="Red Team intelligence briefing for Blue Team developers",
    response_description=(
        "Human-readable JSON briefing: immediate actions, monitoring items, "
        "top exploitable features, and context multiplier risks."
    ),
)
async def get_briefing(
    _key: str = Depends(require_api_key),
) -> dict[str, Any]:
    """
    Return a single synthesised intelligence briefing from the entire evasion KB.

    **Sections:**
    - `immediate_action_required` — CRITICAL evasions with confirmed evasion_success.
      Each item includes a plain-English title, what was found, what to change, and
      which Blue Team file to edit.
    - `monitor` — HIGH-severity evasions requiring attention but not immediate patching.
    - `structural_findings` — Structural evasion patterns identified — shadow scorer offline, severity unconfirmed. Review recommended.
    - `top_exploitable_features` — the 3 most frequently exploited features across all mutations.
    - `context_multipliers_at_risk` — Indian context multipliers that were successfully abused.

    **Golden invariant:** This endpoint returns developer intelligence only.
    It does not trigger any automated action.
    """
    return build_briefing()
