"""
Alert generation service.

Five independent detectors — all return a list of newly created alert IDs:

  check_narrative_spikes()       — post-volume multiplier + momentum
  check_hashtag_surges()         — per-hashtag volume spike (z-score gated)
  check_sentiment_shifts()       — absolute high-negativity + delta shift
  check_influencer_amplification() — verified/high-influence accounts in narratives
  check_viral_content()          — single-post engagement z-score outliers
  check_coordinated_behavior()   — narratives flagged by coordination detector

Notifications are handled separately by NotificationDispatcher
(called from background_tasks after the checks complete).
"""
import numpy as np
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional

from app.core.config import settings
from app.core.database import get_supabase
import structlog

log = structlog.get_logger()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _severity_from_threat(threat_level: int) -> str:
    if threat_level >= 8:
        return "critical"
    if threat_level >= 5:
        return "high"
    if threat_level >= 3:
        return "medium"
    return "low"


def _dedup(db, source_id: str, alert_type: str, cooldown_hours: int = 2) -> bool:
    """Return True if an active alert of this type for this source already exists."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)).isoformat()
    result = (
        db.table("alerts")
        .select("id")
        .eq("source_id", source_id)
        .eq("alert_type", alert_type)
        .eq("status", "active")
        .gte("created_at", cutoff)
        .limit(1)
        .execute()
    )
    return bool(result.data)


def _insert_alert(db, alert: Dict[str, Any]) -> Optional[str]:
    result = db.table("alerts").insert(alert).execute()
    if result.data:
        alert_id = result.data[0]["id"]
        log.info(
            "Alert created",
            alert_type=alert.get("alert_type"),
            severity=alert.get("severity"),
            alert_id=alert_id,
        )
        return alert_id
    return None


# ── Detector 1: Narrative spikes ─────────────────────────────────────────────

async def check_narrative_spikes() -> List[str]:
    """
    Alert when a narrative's post volume in the current hour is ≥
    EMERGING_SPIKE_MULTIPLIER × the previous 2-hour average AND
    the absolute count is ≥ 10 posts.

    Also fires on high momentum_score (≥ 60) for emerging narratives.
    """
    db = get_supabase()
    now = datetime.now(timezone.utc)
    window_current = now - timedelta(hours=1)
    window_previous = now - timedelta(hours=3)

    narratives = (
        db.table("narratives")
        .select("id, title, threat_level, momentum_score, status")
        .in_("status", ["emerging", "active"])
        .execute()
    ).data or []

    created: List[str] = []

    for narrative in narratives:
        nid = narrative["id"]

        # ── Volume-spike check ───────────────────────────────────────────
        curr = (
            db.table("post_narratives")
            .select("post_id", count="exact")
            .eq("narrative_id", nid)
            .gte("assigned_at", window_current.isoformat())
            .execute()
        )
        prev = (
            db.table("post_narratives")
            .select("post_id", count="exact")
            .eq("narrative_id", nid)
            .gte("assigned_at", window_previous.isoformat())
            .lt("assigned_at", window_current.isoformat())
            .execute()
        )

        curr_count = curr.count or 0
        prev_rate  = (prev.count or 0) / 2.0  # normalise 2-h window → 1-h rate

        volume_spike = (
            prev_rate > 0
            and curr_count >= prev_rate * settings.EMERGING_SPIKE_MULTIPLIER
            and curr_count >= 10
        )

        # ── Momentum-spike check (narrative already has timeline data) ───
        momentum = narrative.get("momentum_score") or 0
        momentum_spike = (
            momentum >= 60
            and narrative["status"] == "emerging"
            and curr_count >= 5
        )

        if not (volume_spike or momentum_spike):
            continue

        if _dedup(db, nid, "narrative_spike", cooldown_hours=2):
            continue

        multiplier = curr_count / max(prev_rate, 1)
        severity = _severity_from_threat(narrative.get("threat_level") or 0)
        if volume_spike and multiplier >= 5:
            severity = "critical" if severity in ("high", "critical") else "high"

        reason = (
            f"Post volume spiked {multiplier:.1f}× (last hour: {curr_count} posts)"
            if volume_spike
            else f"Momentum score {momentum:.0f}/100 — narrative is accelerating"
        )

        alert_id = _insert_alert(db, {
            "title": f"Narrative Spike: {narrative['title']}",
            "description": reason,
            "severity": severity,
            "status": "active",
            "alert_type": "narrative_spike",
            "source_id": nid,
            "source_type": "narrative",
            "trigger_data": {
                "current_count": curr_count,
                "previous_rate": round(prev_rate, 1),
                "multiplier": round(multiplier, 2),
                "momentum_score": momentum,
                "threat_level": narrative.get("threat_level"),
            },
            "post_count": curr_count,
        })
        if alert_id:
            created.append(alert_id)

    return created


# ── Detector 2: Hashtag surges ────────────────────────────────────────────────

async def check_hashtag_surges() -> List[str]:
    """
    Alert when a hashtag's current-hour count is ≥ EMERGING_SPIKE_MULTIPLIER
    × the 2-hour baseline rate AND the count is ≥ 20 mentions.
    """
    db = get_supabase()
    now = datetime.now(timezone.utc)
    current_bucket = now.replace(minute=0, second=0, microsecond=0)
    prev3_bucket   = current_bucket - timedelta(hours=3)

    trends = (
        db.table("hashtag_trends")
        .select("hashtag_id, bucket, count")
        .gte("bucket", prev3_bucket.isoformat())
        .execute()
    ).data or []

    hashtag_data: Dict[str, Dict] = {}
    for t in trends:
        hid = t["hashtag_id"]
        if hid not in hashtag_data:
            hashtag_data[hid] = {"current": 0, "previous": 0}
        if t["bucket"] >= current_bucket.isoformat():
            hashtag_data[hid]["current"] += t["count"]
        else:
            hashtag_data[hid]["previous"] += t["count"]

    created: List[str] = []

    for hid, data in hashtag_data.items():
        curr = data["current"]
        prev = data["previous"] / 2.0  # normalise

        if not (prev > 5 and curr >= prev * settings.EMERGING_SPIKE_MULTIPLIER and curr >= 20):
            continue

        tag_result = (
            db.table("hashtags").select("tag").eq("id", hid).single().execute()
        )
        tag = (tag_result.data or {}).get("tag", "unknown")

        # Dedup via source_id = hashtag.id
        if _dedup(db, hid, "hashtag_surge", cooldown_hours=2):
            continue

        multiplier = curr / max(prev, 1)
        severity   = "critical" if curr > 500 else "high" if curr > 100 else "medium"

        alert_id = _insert_alert(db, {
            "title": f"Hashtag Surge: #{tag}",
            "description": (
                f"#{tag} volume rose {multiplier:.1f}× "
                f"({curr} mentions in the last hour)"
            ),
            "severity": severity,
            "status": "active",
            "alert_type": "hashtag_surge",
            "source_id": hid,
            "source_type": "hashtag",
            "trigger_data": {
                "hashtag": tag,
                "current_count": curr,
                "previous_rate": round(prev, 1),
                "multiplier": round(multiplier, 2),
            },
            "post_count": curr,
        })
        if alert_id:
            created.append(alert_id)

    return created


# ── Detector 3: Sentiment shifts ──────────────────────────────────────────────

async def check_sentiment_shifts() -> List[str]:
    """
    Two sub-detectors:

    A) Sustained negativity — cumulative sentiment_distribution > 70 % negative
       (must have ≥ 20 posts).

    B) Rapid shift — recent 1-h window is ≥ 25 percentage-points more negative
       than the preceding 2-h window (both windows must have ≥ 5 posts).
    """
    db = get_supabase()
    now = datetime.now(timezone.utc)
    window_current = now - timedelta(hours=1)
    window_prev    = now - timedelta(hours=3)
    created: List[str] = []

    narratives = (
        db.table("narratives")
        .select("id, title, sentiment_distribution")
        .in_("status", ["active", "emerging"])
        .execute()
    ).data or []

    for narrative in narratives:
        nid  = narrative["id"]
        dist = narrative.get("sentiment_distribution") or {}
        total = sum((dist.get(k, 0) for k in ("positive", "negative", "neutral", "mixed")))

        # ── A: Sustained high negativity ─────────────────────────────────
        if total >= 20:
            neg_pct = dist.get("negative", 0) / total
            if neg_pct > 0.70 and not _dedup(db, nid, "sentiment_shift", cooldown_hours=4):
                alert_id = _insert_alert(db, {
                    "title": f"Negative Sentiment Surge: {narrative['title']}",
                    "description": (
                        f"{neg_pct:.0%} of posts carry negative sentiment "
                        f"(threshold: 70 %)"
                    ),
                    "severity": "critical" if neg_pct > 0.88 else "high" if neg_pct > 0.80 else "medium",
                    "status": "active",
                    "alert_type": "sentiment_shift",
                    "source_id": nid,
                    "source_type": "narrative",
                    "trigger_data": {
                        "sub_type": "sustained_negativity",
                        "negative_pct": round(neg_pct, 3),
                        "distribution": dist,
                        "total_posts": total,
                    },
                })
                if alert_id:
                    created.append(alert_id)
                continue  # don't double-fire delta check on same narrative

        # ── B: Rapid delta shift ─────────────────────────────────────────
        # Fetch post sentiments in each window via post_narratives join
        def _sentiment_pct(posts_data: List[Dict]) -> float:
            if not posts_data:
                return 0.0
            neg = sum(1 for p in posts_data if p.get("sentiment") == "negative")
            return neg / len(posts_data)

        curr_pn = (
            db.table("post_narratives")
            .select("post_id")
            .eq("narrative_id", nid)
            .gte("assigned_at", window_current.isoformat())
            .execute()
        ).data or []

        prev_pn = (
            db.table("post_narratives")
            .select("post_id")
            .eq("narrative_id", nid)
            .gte("assigned_at", window_prev.isoformat())
            .lt("assigned_at", window_current.isoformat())
            .execute()
        ).data or []

        if len(curr_pn) < 5 or len(prev_pn) < 5:
            continue

        def _fetch_sentiments(post_ids: List[str]) -> List[Dict]:
            return (
                db.table("posts")
                .select("id, sentiment")
                .in_("id", [r["post_id"] for r in post_ids])
                .execute()
            ).data or []

        curr_neg = _sentiment_pct(_fetch_sentiments(curr_pn))
        prev_neg = _sentiment_pct(_fetch_sentiments(prev_pn))
        delta = curr_neg - prev_neg

        if delta >= 0.25 and curr_neg >= 0.50:
            if not _dedup(db, nid, "sentiment_shift", cooldown_hours=4):
                alert_id = _insert_alert(db, {
                    "title": f"Rapid Sentiment Deterioration: {narrative['title']}",
                    "description": (
                        f"Negative sentiment rose {delta:.0%} in one hour "
                        f"(from {prev_neg:.0%} → {curr_neg:.0%})"
                    ),
                    "severity": "high" if delta >= 0.40 else "medium",
                    "status": "active",
                    "alert_type": "sentiment_shift",
                    "source_id": nid,
                    "source_type": "narrative",
                    "trigger_data": {
                        "sub_type": "rapid_delta",
                        "previous_neg_pct": round(prev_neg, 3),
                        "current_neg_pct": round(curr_neg, 3),
                        "delta": round(delta, 3),
                    },
                })
                if alert_id:
                    created.append(alert_id)

    return created


# ── Detector 4: Influencer amplification ─────────────────────────────────────

async def check_influencer_amplification() -> List[str]:
    """
    Alert when a monitored high-influence (score ≥ 70) or flagged account
    has posted content that was assigned to an active/emerging narrative
    within the last 2 hours.
    """
    db = get_supabase()
    now = datetime.now(timezone.utc)
    window = now - timedelta(hours=2)
    created: List[str] = []

    # High-influence or flagged accounts that are monitored
    influencers = (
        db.table("influencers")
        .select("id, platform, platform_user_id, username, display_name, influence_score, followers_count, is_flagged")
        .eq("is_monitored", True)
        .or_("influence_score.gte.70,is_flagged.eq.true")
        .execute()
    ).data or []

    if not influencers:
        return []

    author_ids    = [inf["platform_user_id"] for inf in influencers]
    influencer_map = {inf["platform_user_id"]: inf for inf in influencers}

    recent_posts = (
        db.table("posts")
        .select("id, author_id, author_username, platform, engagement_score, posted_at")
        .in_("author_id", author_ids)
        .gte("posted_at", window.isoformat())
        .execute()
    ).data or []

    if not recent_posts:
        return []

    post_ids = [p["id"] for p in recent_posts]
    post_map = {p["id"]: p for p in recent_posts}

    # Which of those posts are in active narratives?
    links = (
        db.table("post_narratives")
        .select("post_id, narrative_id")
        .in_("post_id", post_ids)
        .execute()
    ).data or []

    if not links:
        return []

    # Fetch affected narratives
    narrative_ids = list({lnk["narrative_id"] for lnk in links})
    narratives_result = (
        db.table("narratives")
        .select("id, title, threat_level, status")
        .in_("id", narrative_ids)
        .in_("status", ["active", "emerging"])
        .execute()
    ).data or []
    narrative_map = {n["id"]: n for n in narratives_result}

    seen_pairs: set = set()

    for link in links:
        narrative = narrative_map.get(link["narrative_id"])
        post      = post_map.get(link["post_id"])
        if not narrative or not post:
            continue

        influencer = influencer_map.get(post["author_id"])
        if not influencer:
            continue

        pair = (influencer["id"], narrative["id"])
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        # Dedup: max 1 alert per influencer per 4h
        if _dedup(db, influencer["id"], "influencer_activity", cooldown_hours=4):
            continue

        severity = (
            "critical" if influencer["is_flagged"] and (narrative.get("threat_level") or 0) >= 6
            else "high" if influencer["is_flagged"] or (influencer.get("influence_score") or 0) >= 85
            else "medium"
        )
        followers = influencer.get("followers_count") or 0
        display   = influencer.get("display_name") or influencer["username"]

        alert_id = _insert_alert(db, {
            "title": f"Influencer Amplification: @{influencer['username']}",
            "description": (
                f"@{influencer['username']} ({followers:,} followers) is amplifying "
                f"the narrative \"{narrative['title']}\""
            ),
            "severity": severity,
            "status": "active",
            "alert_type": "influencer_activity",
            "source_id": influencer["id"],
            "source_type": "influencer",
            "trigger_data": {
                "influencer_id":       influencer["id"],
                "influencer_username": influencer["username"],
                "display_name":        display,
                "followers_count":     followers,
                "influence_score":     influencer.get("influence_score"),
                "is_flagged":          influencer.get("is_flagged"),
                "narrative_id":        narrative["id"],
                "narrative_title":     narrative["title"],
                "narrative_threat":    narrative.get("threat_level"),
                "post_id":             post["id"],
                "engagement_score":    post.get("engagement_score"),
            },
            "affected_platforms": [post.get("platform", "other")],
        })
        if alert_id:
            created.append(alert_id)

    return created


# ── Detector 5: Viral content ─────────────────────────────────────────────────

async def check_viral_content() -> List[str]:
    """
    Alert when a single post's engagement is a statistical outlier:
    z-score ≥ 3σ above the platform mean for the last 24 hours,
    AND the post was published in the last 6 hours.
    Requires ≥ 15 posts per platform to compute a meaningful baseline.
    """
    db = get_supabase()
    now = datetime.now(timezone.utc)
    baseline_window = now - timedelta(hours=24)
    recent_window   = now - timedelta(hours=6)
    created: List[str] = []

    posts = (
        db.table("posts")
        .select("id, platform, engagement_score, author_username, author_followers, posted_at, url")
        .gte("posted_at", baseline_window.isoformat())
        .not_.is_("engagement_score", "null")
        .execute()
    ).data or []

    if len(posts) < 15:
        return []

    by_platform: Dict[str, List[Dict]] = defaultdict(list)
    for p in posts:
        by_platform[p["platform"]].append(p)

    for platform, platform_posts in by_platform.items():
        if len(platform_posts) < 15:
            continue

        scores = np.array([p["engagement_score"] for p in platform_posts], dtype=float)
        mean   = float(np.mean(scores))
        std    = float(np.std(scores))
        if std < 1e-6:
            continue

        threshold = mean + 3.0 * std

        for post in platform_posts:
            if post["posted_at"] < recent_window.isoformat():
                continue
            if post["engagement_score"] < threshold:
                continue

            # Already have an alert for this post?
            if _dedup(db, post["id"], "viral_content", cooldown_hours=24):
                continue

            z_score  = (post["engagement_score"] - mean) / std
            severity = (
                "critical" if z_score > 6
                else "high"  if z_score > 4
                else "medium"
            )
            author = post.get("author_username") or "unknown"

            alert_id = _insert_alert(db, {
                "title": f"Viral Content: @{author} on {platform}",
                "description": (
                    f"Post has {z_score:.1f}σ above-average engagement on {platform} "
                    f"(score {post['engagement_score']:.0f} vs platform avg {mean:.0f})"
                ),
                "severity": severity,
                "status": "active",
                "alert_type": "viral_content",
                "source_id": post["id"],
                "source_type": "post",
                "trigger_data": {
                    "post_id":          post["id"],
                    "platform":         platform,
                    "engagement_score": post["engagement_score"],
                    "z_score":          round(z_score, 2),
                    "platform_mean":    round(mean, 2),
                    "platform_std":     round(std, 2),
                    "author_username":  author,
                    "author_followers": post.get("author_followers"),
                    "url":              post.get("url"),
                },
                "affected_platforms": [platform],
                "post_count": 1,
            })
            if alert_id:
                created.append(alert_id)

    return created


# ── Detector 6: Coordinated behavior ─────────────────────────────────────────

async def check_coordinated_behavior() -> List[str]:
    """
    Alert when a narrative's coordination_score ≥ 0.5 (set by the
    narrative clustering service) and the narrative is active/emerging.
    """
    db = get_supabase()
    now = datetime.now(timezone.utc)
    created: List[str] = []

    narratives = (
        db.table("narratives")
        .select("id, title, coordination_score, coordination_signals, threat_level")
        .in_("status", ["active", "emerging"])
        .gte("coordination_score", 0.5)
        .execute()
    ).data or []

    for narrative in narratives:
        nid = narrative["id"]
        if _dedup(db, nid, "coordinated_behavior", cooldown_hours=6):
            continue

        score   = narrative.get("coordination_score") or 0
        signals = narrative.get("coordination_signals") or []
        signal_labels = [s.get("type", "").replace("_", " ") for s in signals]
        severity = (
            "critical" if score >= 0.80
            else "high" if score >= 0.65
            else "medium"
        )

        alert_id = _insert_alert(db, {
            "title": f"Coordinated Activity Detected: {narrative['title']}",
            "description": (
                f"Coordination score {score:.0%} — signals: "
                f"{', '.join(signal_labels) or 'burst timing, near-duplicate content'}"
            ),
            "severity": severity,
            "status": "active",
            "alert_type": "coordinated_behavior",
            "source_id": nid,
            "source_type": "narrative",
            "trigger_data": {
                "narrative_id":       nid,
                "coordination_score": round(score, 3),
                "signals":            signals,
                "threat_level":       narrative.get("threat_level"),
            },
        })
        if alert_id:
            created.append(alert_id)

    return created


# ── Legacy keyword-match helper (called from ingestion service) ───────────────

async def check_keyword_matches(content: str, post_id: str) -> List[str]:
    """Check post content against active watch terms (called post-ingestion)."""
    db = get_supabase()
    terms = (
        db.table("watch_terms")
        .select("*")
        .eq("is_active", True)
        .eq("alert_on_match", True)
        .execute()
    ).data or []

    created: List[str] = []
    content_lower = content.lower()

    for term in terms:
        if term["term"].lower() not in content_lower:
            continue

        db.table("watch_terms").update(
            {"match_count": term["match_count"] + 1}
        ).eq("id", term["id"]).execute()

        alert_id = _insert_alert(db, {
            "title":       f"Watch Term Match: \"{term['term']}\"",
            "description": f"Post contains monitored term: \"{term['term']}\"",
            "severity":    term.get("alert_severity", "medium"),
            "status":      "active",
            "alert_type":  "keyword_match",
            "source_id":   post_id,
            "source_type": "post",
            "trigger_data": {
                "term":     term["term"],
                "category": term.get("category"),
                "post_id":  post_id,
            },
        })
        if alert_id:
            created.append(alert_id)

    return created
