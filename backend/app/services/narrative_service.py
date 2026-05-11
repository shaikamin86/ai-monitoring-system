"""
Narrative clustering, tracking, and analysis service.

Enhanced semantic pipeline:
- DBSCAN clustering on OpenAI text-embedding-3-small vectors
- Velocity-based momentum scoring (current-hour vs 6-hour rolling baseline)
- Coordinated inauthentic behavior detection (burst timing, near-duplicate
  content, account concentration)
- Cross-narrative merging for near-duplicate clusters (cosine ≥ 0.92)
- Soft "related" linking for semantically adjacent clusters (cosine ≥ 0.75)
- Weighted centroid updates (proportional to post counts)
- Hourly narrative_timeline snapshots via SQL RPC (additive upsert)
"""
import asyncio
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import normalize
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import json

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.database import get_supabase
from app.services.embedding_service import cosine_similarity, compute_centroid
import structlog

log = structlog.get_logger()

# ── Clustering thresholds ────────────────────────────────────────────────────
_MERGE_THRESHOLD   = 0.92   # auto-merge two narrative clusters
_RELATED_THRESHOLD = 0.75   # soft-link as semantically related

# ── Coordination detection thresholds ───────────────────────────────────────
_BURST_WINDOW_MIN        = 30    # minutes per burst window
_BURST_UNIQUE_AUTHORS    = 8     # distinct accounts in window → burst signal
_NEAR_DUPE_SIM           = 0.95  # cosine sim threshold for "near-duplicate"
_NEAR_DUPE_PAIR_FLOOR    = 3     # min cross-account near-dupe pairs to flag
_CONCENTRATION_THRESHOLD = 0.30  # top-author share above this → flag


# ── Public API ───────────────────────────────────────────────────────────────

async def cluster_unassigned_posts(batch_size: int = 200) -> Dict[str, Any]:
    """
    Fetch unassigned posts from last 48 h, cluster by embedding similarity,
    merge clusters into existing narratives or create new ones.

    After assignment:
    - Writes hourly timeline buckets (additive via SQL RPC).
    - Recomputes momentum + coordination scores for all touched narratives.
    """
    db = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()

    posts_result = (
        db.table("posts")
        .select(
            "id, content, embedding, language, sentiment, sentiment_score,"
            " posted_at, author_id, platform, engagement_score"
        )
        .gte("posted_at", cutoff)
        .not_.is_("embedding", "null")
        .execute()
    )
    posts = posts_result.data or []

    assigned_result = (
        db.table("post_narratives")
        .select("post_id")
        .gte("assigned_at", cutoff)
        .execute()
    )
    assigned_ids = {r["post_id"] for r in (assigned_result.data or [])}
    unassigned = [p for p in posts if p["id"] not in assigned_ids]

    if len(unassigned) < 3:
        return {"clusters_found": 0, "posts_processed": len(unassigned)}

    embeddings = [p["embedding"] for p in unassigned]
    matrix_norm = normalize(np.array(embeddings))

    eps = 1.0 - settings.NARRATIVE_SIMILARITY_THRESHOLD
    clustering = DBSCAN(eps=eps, min_samples=3, metric="cosine").fit(matrix_norm)
    labels = clustering.labels_

    unique_labels = set(labels) - {-1}
    clusters_found = 0
    updated_narratives: Dict[str, List[Dict]] = {}

    for label in unique_labels:
        indices = np.where(labels == label)[0]
        cluster_posts = [unassigned[i] for i in indices]
        cluster_embeddings = [embeddings[i] for i in indices]
        centroid = compute_centroid(cluster_embeddings)

        narrative_id = await _match_or_create_narrative(db, cluster_posts, centroid)
        if not narrative_id:
            continue

        assignments = [
            {
                "post_id": cluster_posts[k]["id"],
                "narrative_id": narrative_id,
                "similarity_score": cosine_similarity(cluster_embeddings[k], centroid),
            }
            for k in range(len(cluster_posts))
        ]
        db.table("post_narratives").upsert(assignments).execute()
        db.rpc("update_narrative_stats", {"p_narrative_id": narrative_id}).execute()
        updated_narratives.setdefault(narrative_id, []).extend(cluster_posts)
        clusters_found += 1

    # Timeline + metrics update for all touched narratives
    for narrative_id, narrative_posts in updated_narratives.items():
        _write_timeline_bucket(db, narrative_id, narrative_posts)

    if updated_narratives:
        await _batch_update_narrative_metrics(db, list(updated_narratives.keys()))

    return {
        "clusters_found": clusters_found,
        "posts_processed": len(unassigned),
        "narratives_updated": len(updated_narratives),
    }


async def update_narrative_statuses() -> None:
    """
    Periodic task (every 30 min):
    - Transition narrative statuses based on last_activity recency.
    - Refresh momentum + coordination for all active/emerging narratives.
    - Merge or soft-link near-duplicate narrative clusters.
    """
    db = get_supabase()
    now = datetime.now(timezone.utc)

    thresholds = {
        "dormant":   now - timedelta(days=7),
        "declining": now - timedelta(hours=24),
        "active":    now - timedelta(hours=6),
    }

    for status, threshold in thresholds.items():
        query = (
            db.table("narratives")
            .select("id")
            .lt("last_activity", threshold.isoformat())
        )
        if status == "active":
            query = query.gte("last_activity", thresholds["declining"].isoformat())
        elif status == "declining":
            query = query.gte("last_activity", thresholds["dormant"].isoformat())

        result = query.execute()
        ids = [r["id"] for r in (result.data or [])]
        if ids:
            db.table("narratives").update({"status": status}).in_("id", ids).execute()

    # Refresh metrics for live narratives
    live_result = (
        db.table("narratives")
        .select("id")
        .in_("status", ["emerging", "active"])
        .execute()
    )
    live_ids = [r["id"] for r in (live_result.data or [])]
    if live_ids:
        await _batch_update_narrative_metrics(db, live_ids)


async def merge_related_narratives() -> Dict[str, Any]:
    """
    Scan active/emerging narratives for semantically overlapping clusters.

    - cosine ≥ _MERGE_THRESHOLD  → auto-merge smaller into larger
    - cosine ≥ _RELATED_THRESHOLD → soft-link as related_narrative_ids

    Returns {"merged": int, "linked": int}.
    """
    db = get_supabase()
    result = (
        db.table("narratives")
        .select("id, centroid_embedding, post_count, status, related_narrative_ids")
        .in_("status", ["emerging", "active"])
        .not_.is_("centroid_embedding", "null")
        .execute()
    )
    narratives = result.data or []
    if len(narratives) < 2:
        return {"merged": 0, "linked": 0}

    merged_ids: set = set()
    merged_count = linked_count = 0

    for i, n1 in enumerate(narratives):
        if n1["id"] in merged_ids:
            continue
        for j, n2 in enumerate(narratives):
            if i >= j or n2["id"] in merged_ids:
                continue

            sim = cosine_similarity(
                n1["centroid_embedding"], n2["centroid_embedding"]
            )

            if sim >= _MERGE_THRESHOLD:
                # Keep the larger narrative by post_count
                if (n1.get("post_count") or 0) >= (n2.get("post_count") or 0):
                    keep_id, drop_id = n1["id"], n2["id"]
                else:
                    keep_id, drop_id = n2["id"], n1["id"]
                _execute_merge(db, keep_id, drop_id)
                merged_ids.add(drop_id)
                merged_count += 1
                log.info(
                    "Merged narrative clusters",
                    keep=keep_id,
                    dropped=drop_id,
                    similarity=round(sim, 4),
                )

            elif sim >= _RELATED_THRESHOLD:
                _link_related(db, n1["id"], n2["id"])
                linked_count += 1

    return {"merged": merged_count, "linked": linked_count}


# ── Internal helpers ─────────────────────────────────────────────────────────

async def _match_or_create_narrative(
    db, cluster_posts: List[Dict], centroid: List[float]
) -> Optional[str]:
    """
    Find the closest active/emerging narrative whose centroid is within
    NARRATIVE_SIMILARITY_THRESHOLD, weighted-update its centroid, and
    return its ID.  If no match, create a new narrative.
    """
    result = (
        db.table("narratives")
        .select("id, centroid_embedding, title, status, post_count")
        .in_("status", ["emerging", "active"])
        .execute()
    )
    existing = result.data or []

    best_match_id: Optional[str] = None
    best_match_post_count = 0
    best_similarity = 0.0

    for narrative in existing:
        if not narrative.get("centroid_embedding"):
            continue
        sim = cosine_similarity(centroid, narrative["centroid_embedding"])
        if sim > settings.NARRATIVE_SIMILARITY_THRESHOLD and sim > best_similarity:
            best_similarity = sim
            best_match_id = narrative["id"]
            best_match_post_count = narrative.get("post_count") or 0

    if best_match_id:
        old_result = (
            db.table("narratives")
            .select("centroid_embedding")
            .eq("id", best_match_id)
            .single()
            .execute()
        )
        old_centroid = old_result.data.get("centroid_embedding") or []

        if old_centroid:
            # Weighted blend: proportional to post counts
            total = best_match_post_count + len(cluster_posts)
            w_old = best_match_post_count / total
            w_new = len(cluster_posts) / total
            blended = np.array(old_centroid) * w_old + np.array(centroid) * w_new
            norm = np.linalg.norm(blended)
            new_centroid = (blended / norm).tolist() if norm > 0 else centroid
        else:
            new_centroid = centroid

        db.table("narratives").update(
            {"centroid_embedding": new_centroid}
        ).eq("id", best_match_id).execute()
        return best_match_id

    # ── Create a new narrative ────────────────────────────────────────────
    title, summary, themes = await _generate_narrative_metadata(cluster_posts)

    hashtags: List[str] = []
    for post in cluster_posts:
        hashtags.extend(post.get("hashtags") or [])
    top_hashtags = list(dict.fromkeys(hashtags))[:10]  # preserve order, deduplicate

    threat_level = _compute_threat_level(cluster_posts, themes)
    virality = _compute_virality_score(cluster_posts)

    lang_dist: Dict[str, int] = {}
    platform_dist: Dict[str, int] = {}
    for post in cluster_posts:
        lang = post.get("language") or "en"
        platform = post.get("platform") or "other"
        lang_dist[lang] = lang_dist.get(lang, 0) + 1
        platform_dist[platform] = platform_dist.get(platform, 0) + 1

    new_narrative = {
        "title": title,
        "summary": summary,
        "key_themes": themes,
        "key_hashtags": top_hashtags,
        "centroid_embedding": centroid,
        "status": "emerging",
        "post_count": len(cluster_posts),
        "unique_authors": len({p.get("author_id") for p in cluster_posts} - {None}),
        "threat_level": threat_level,
        "virality_score": virality,
        "languages": lang_dist,
        "platforms": platform_dist,
        "first_detected": datetime.now(timezone.utc).isoformat(),
        "last_activity": datetime.now(timezone.utc).isoformat(),
    }

    insert_result = db.table("narratives").insert(new_narrative).execute()
    return insert_result.data[0]["id"] if insert_result.data else None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def _generate_narrative_metadata(
    posts: List[Dict],
) -> Tuple[str, str, List[str]]:
    """Call GPT-4o-mini to produce a title, summary, and theme list."""
    sample = "\n---\n".join(p.get("content", "")[:300] for p in posts[:8])

    prompt = (
        "Analyze these Malaysian social media posts and return a JSON narrative profile.\n\n"
        f"Posts:\n{sample}\n\n"
        "Return JSON:\n"
        '{"title": "concise narrative title (max 80 chars)",'
        ' "summary": "2-3 sentence summary",'
        ' "themes": ["theme1", "theme2", "theme3"]}'
    )

    response = await AsyncOpenAI(api_key=settings.OPENAI_API_KEY).chat.completions.create(
        model=settings.OPENAI_CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=400,
    )
    data = json.loads(response.choices[0].message.content)
    return (
        data.get("title") or "Untitled Narrative",
        data.get("summary") or "",
        data.get("themes") or [],
    )


def _compute_threat_level(posts: List[Dict], themes: List[str]) -> int:
    """0-10 threat level derived from content keywords and sentiment."""
    threat_keywords = [
        "rusuhan", "darurat", "ancaman", "bahaya", "serangan",
        "riot", "emergency", "threat", "attack", "crisis",
        "racial", "kaum", "agama", "religion", "extremis",
    ]
    content_all = " ".join(p.get("content", "").lower() for p in posts)
    theme_all = " ".join(t.lower() for t in themes)

    keyword_hits = sum(
        1 for kw in threat_keywords if kw in content_all or kw in theme_all
    )
    neg_ratio = sum(
        1 for p in posts if p.get("sentiment") == "negative"
    ) / max(len(posts), 1)

    base = min(5, keyword_hits)
    sentiment_boost = int(neg_ratio * 3)
    volume_boost = 1 if len(posts) > 50 else 0
    return min(10, base + sentiment_boost + volume_boost)


def _compute_virality_score(posts: List[Dict]) -> float:
    """0-100 virality score."""
    if not posts:
        return 0.0
    total_engagement = sum(p.get("engagement_score") or 0 for p in posts)
    unique_authors = len({p.get("author_id") for p in posts} - {None})
    velocity = len(posts)
    return min(100.0, total_engagement * 0.5 + unique_authors * 2 + velocity * 0.5)


# ── Timeline & metrics ───────────────────────────────────────────────────────

def _write_timeline_bucket(db, narrative_id: str, posts: List[Dict]) -> None:
    """
    Upsert an hourly timeline bucket via the SQL RPC (additive semantics:
    post_count and engagement are incremented on conflict).
    """
    bucket = datetime.now(timezone.utc).replace(
        minute=0, second=0, microsecond=0
    )
    new_authors = len({p.get("author_id") for p in posts} - {None})
    engagement = sum(p.get("engagement_score") or 0 for p in posts)
    sentiments = [
        p["sentiment_score"]
        for p in posts
        if p.get("sentiment_score") is not None
    ]
    sentiment_avg = float(np.mean(sentiments)) if sentiments else 0.0

    try:
        db.rpc(
            "upsert_narrative_timeline",
            {
                "p_narrative_id": narrative_id,
                "p_bucket": bucket.isoformat(),
                "p_post_count": len(posts),
                "p_new_authors": new_authors,
                "p_engagement": engagement,
                "p_sentiment": sentiment_avg,
            },
        ).execute()
    except Exception as exc:
        log.warning("Timeline upsert failed", narrative=narrative_id, error=str(exc))


async def _compute_narrative_momentum(db, narrative_id: str) -> float:
    """
    Velocity-based momentum in [-100, 100].

    Formula:
        momentum = (current_hour_posts - baseline_avg) / baseline_avg * 100
    where baseline_avg is the mean of the previous 6 complete hourly buckets.
    If there is no baseline data, returns current_count * 10 (capped at 100).
    """
    now_hour = datetime.now(timezone.utc).replace(
        minute=0, second=0, microsecond=0
    )
    baseline_start = now_hour - timedelta(hours=7)
    baseline_end = now_hour  # exclusive

    timeline_result = (
        db.table("narrative_timeline")
        .select("bucket, post_count")
        .eq("narrative_id", narrative_id)
        .gte("bucket", baseline_start.isoformat())
        .lt("bucket", (now_hour + timedelta(hours=1)).isoformat())
        .execute()
    )
    rows = timeline_result.data or []

    current_count = sum(
        r["post_count"]
        for r in rows
        if r["bucket"] >= now_hour.isoformat()
    )
    baseline_counts = [
        r["post_count"]
        for r in rows
        if baseline_start.isoformat() <= r["bucket"] < baseline_end.isoformat()
    ]
    baseline_avg = sum(baseline_counts) / max(len(baseline_counts), 1)

    if baseline_avg == 0:
        return min(100.0, current_count * 10.0)
    momentum = (current_count - baseline_avg) / baseline_avg * 100.0
    return max(-100.0, min(100.0, round(momentum, 2)))


async def _detect_coordinated_messaging(db, narrative_id: str) -> Dict[str, Any]:
    """
    Score a narrative for coordinated inauthentic behavior [0.0 – 1.0].

    Three independent signals (weighted sum):
    1. Burst timing (40 %): ≥ _BURST_UNIQUE_AUTHORS distinct accounts post
       within the same 30-minute window.
    2. Near-duplicate content (40 %): ≥ _NEAR_DUPE_PAIR_FLOOR cross-account
       pairs with cosine similarity > _NEAR_DUPE_SIM.
    3. Account concentration (20 %): one account contributes > 30 % of all
       posts in the narrative while total unique authors < 5.

    Returns {"score": float, "signals": List[dict]}.
    """
    # Collect post IDs for this narrative
    pn_result = (
        db.table("post_narratives")
        .select("post_id")
        .eq("narrative_id", narrative_id)
        .execute()
    )
    post_ids = [r["post_id"] for r in (pn_result.data or [])]

    if len(post_ids) < 5:
        return {"score": 0.0, "signals": []}

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    posts_result = (
        db.table("posts")
        .select("id, author_id, posted_at, embedding, engagement_score")
        .in_("id", post_ids[:100])
        .gte("posted_at", cutoff)
        .execute()
    )
    posts = posts_result.data or []

    if len(posts) < 5:
        return {"score": 0.0, "signals": []}

    signals: List[Dict] = []
    weighted_score = 0.0

    # ── Signal 1: Burst timing ────────────────────────────────────────────
    time_buckets: Dict[str, set] = defaultdict(set)
    for post in posts:
        posted_at = post.get("posted_at")
        author_id = post.get("author_id")
        if not posted_at or not author_id:
            continue
        try:
            ts = posted_at.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts)
            bucket_min = (dt.minute // _BURST_WINDOW_MIN) * _BURST_WINDOW_MIN
            bucket_key = dt.replace(
                minute=bucket_min, second=0, microsecond=0
            ).isoformat()
            time_buckets[bucket_key].add(author_id)
        except (ValueError, AttributeError):
            continue

    max_burst = max((len(v) for v in time_buckets.values()), default=0)
    if max_burst >= _BURST_UNIQUE_AUTHORS:
        burst_score = min(1.0, max_burst / 15.0)
        signals.append({
            "type": "burst_timing",
            "unique_authors_in_window": max_burst,
            "window_minutes": _BURST_WINDOW_MIN,
            "score": round(burst_score, 3),
        })
        weighted_score += burst_score * 0.40

    # ── Signal 2: Near-duplicate content from different accounts ──────────
    posts_with_emb = [
        p for p in posts if p.get("embedding") and p.get("author_id")
    ]
    near_dupe_pairs = 0

    if len(posts_with_emb) >= 2:
        emb_arr = np.array([p["embedding"] for p in posts_with_emb])
        norms = np.linalg.norm(emb_arr, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        emb_norm = emb_arr / norms
        sim_matrix = (emb_norm @ emb_norm.T).clip(0, 1)
        authors = [p["author_id"] for p in posts_with_emb]
        n = len(posts_with_emb)
        for i in range(n):
            for j in range(i + 1, n):
                if sim_matrix[i, j] > _NEAR_DUPE_SIM and authors[i] != authors[j]:
                    near_dupe_pairs += 1

    if near_dupe_pairs >= _NEAR_DUPE_PAIR_FLOOR:
        dupe_score = min(1.0, near_dupe_pairs / 10.0)
        signals.append({
            "type": "near_duplicate_content",
            "cross_account_pairs": near_dupe_pairs,
            "similarity_threshold": _NEAR_DUPE_SIM,
            "score": round(dupe_score, 3),
        })
        weighted_score += dupe_score * 0.40

    # ── Signal 3: Account concentration ──────────────────────────────────
    author_counts: Dict[str, int] = defaultdict(int)
    for post in posts:
        if post.get("author_id"):
            author_counts[post["author_id"]] += 1

    if author_counts:
        total = len(posts)
        unique_auth = len(author_counts)
        top_share = max(author_counts.values()) / total
        if top_share > _CONCENTRATION_THRESHOLD and unique_auth < 5:
            conc_score = min(1.0, top_share)
            signals.append({
                "type": "account_concentration",
                "top_author_share": round(top_share, 3),
                "unique_authors": unique_auth,
                "score": round(conc_score, 3),
            })
            weighted_score += conc_score * 0.20

    return {
        "score": round(min(1.0, weighted_score), 3),
        "signals": signals,
    }


async def _batch_update_narrative_metrics(
    db, narrative_ids: List[str]
) -> None:
    """Compute and persist momentum + coordination for a list of narratives."""
    for narrative_id in narrative_ids:
        try:
            momentum = await _compute_narrative_momentum(db, narrative_id)
            coordination = await _detect_coordinated_messaging(db, narrative_id)

            update: Dict[str, Any] = {
                "momentum_score": momentum,
                "coordination_score": coordination["score"],
                "coordination_signals": coordination["signals"],
            }
            if coordination["score"] >= 0.5:
                update["is_coordinated"] = True

            db.table("narratives").update(update).eq("id", narrative_id).execute()
        except Exception as exc:
            log.warning(
                "Narrative metrics update failed",
                narrative=narrative_id,
                error=str(exc),
            )


# ── Narrative merge helpers ──────────────────────────────────────────────────

def _execute_merge(db, keep_id: str, drop_id: str) -> None:
    """
    Merge drop_id narrative into keep_id:
    - Re-assign all post_narratives rows.
    - Refresh stats on the surviving narrative via SQL function.
    - Mark the dropped narrative as dormant with merge metadata.
    """
    db.table("post_narratives").update(
        {"narrative_id": keep_id}
    ).eq("narrative_id", drop_id).execute()

    db.rpc("update_narrative_stats", {"p_narrative_id": keep_id}).execute()

    db.table("narratives").update({
        "status": "dormant",
        "metadata": {"merged_into": keep_id, "merged_at": datetime.now(timezone.utc).isoformat()},
    }).eq("id", drop_id).execute()


def _link_related(db, id1: str, id2: str) -> None:
    """
    Bidirectionally add each narrative to the other's related_narrative_ids
    (no-op if the link already exists).
    """
    for own_id, other_id in [(id1, id2), (id2, id1)]:
        try:
            row = (
                db.table("narratives")
                .select("related_narrative_ids")
                .eq("id", own_id)
                .single()
                .execute()
            )
            current: List[str] = row.data.get("related_narrative_ids") or []
            if other_id not in current:
                db.table("narratives").update(
                    {"related_narrative_ids": current + [other_id]}
                ).eq("id", own_id).execute()
        except Exception as exc:
            log.warning("Failed to link related narratives", own=own_id, other=other_id, error=str(exc))
