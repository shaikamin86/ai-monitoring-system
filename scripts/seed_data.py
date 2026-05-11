#!/usr/bin/env python3
"""
seed_data.py — Realistic Malaysia social media monitoring seed data.

Populates:
  - influencers         (Twitter, TikTok, Facebook, News)
  - posts               (500+ across 5 platforms, last 48h)
  - hashtags            (with trend counts)
  - hashtag_trends      (hourly buckets)
  - post_hashtags       (junction)
  - entities            (persons, orgs, locations, topics)
  - post_entities       (junction)
  - narratives          (10 clusters: political, commodity, cost-of-living, viral)
  - post_narratives     (junction)
  - narrative_timeline  (hourly buckets, last 48h)
  - alerts              (8 active alerts, various severities)
  - analytics_snapshots (last 24 hourly snapshots)

Usage:
    # Install deps first (same virtualenv as backend):
    pip install supabase python-dotenv

    # From project root:
    python scripts/seed_data.py

    # To wipe tables first (fresh seed):
    python scripts/seed_data.py --reset
"""
import argparse
import json
import math
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# ── Env loading ───────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(path): pass  # type: ignore

_root = Path(__file__).parent.parent
for candidate in [_root / ".env", _root / "backend" / ".env"]:
    if candidate.exists():
        load_dotenv(str(candidate))
        break

try:
    from supabase import create_client, Client
except ImportError:
    print("ERROR: supabase package not installed.  Run: pip install supabase")
    sys.exit(1)

SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_KEY not set.  Check .env")
    sys.exit(1)

db: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Helpers ───────────────────────────────────────────────────────────────────
NOW = datetime.now(timezone.utc)
rng = random.Random(42)


def uid() -> str:
    return str(uuid.uuid4())


def ts(hours_ago: float, jitter_min: int = 0) -> str:
    """ISO timestamp N hours ago ± up to jitter_min minutes."""
    delta = timedelta(hours=hours_ago, minutes=rng.uniform(-jitter_min, jitter_min))
    return (NOW - delta).isoformat()


def eng(likes: int, shares: int, comments: int, followers: int) -> float:
    raw = likes + shares * 3 + comments * 2
    rate = raw / max(followers, 1) * 100
    return min(100.0, math.log(max(1, raw) + 1) * 10 + rate)


def insert(table: str, rows: list, upsert_on: Optional[str] = None, chunk: int = 100) -> list:
    if not rows:
        return []
    all_results = []
    for i in range(0, len(rows), chunk):
        batch = rows[i:i + chunk]
        try:
            if upsert_on:
                res = db.table(table).upsert(batch, on_conflict=upsert_on).execute()
            else:
                res = db.table(table).insert(batch).execute()
            all_results.extend(res.data or [])
        except Exception as e:
            print(f"  WARN {table} (batch {i//chunk}): {e}")
    return all_results


def reset_tables():
    """Delete seed data rows (preserves watch_terms seeded by migration)."""
    tables = [
        "analytics_snapshots", "notification_history", "alerts",
        "influencer_activity", "narrative_timeline", "post_narratives",
        "post_entities", "post_hashtags", "hashtag_trends",
        "posts", "narratives", "entities", "hashtags", "influencers",
    ]
    for t in tables:
        try:
            db.table(t).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            print(f"  Cleared {t}")
        except Exception as e:
            print(f"  WARN clearing {t}: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
#  1. INFLUENCERS
# ═══════════════════════════════════════════════════════════════════════════════

INFLUENCERS_RAW = [
    # (platform, user_id, username, display_name, followers, verified, influence, topics, sentiment, bio)
    # ── Twitter/X ──────────────────────────────────────────────────────────────
    ("twitter", "kj_malaysia", "khairykj", "Khairy Jamaluddin", 1_850_000, True, 88.5,
     ["politics", "health", "governance"], "mixed",
     "Former Minister. UMNO. Views my own. Tweeting from KL."),
    ("twitter", "syedsaddiq_x", "syedsaddiq", "Syed Saddiq Syed Abdul Rahman", 1_220_000, True, 85.2,
     ["politics", "youth", "economy"], "negative",
     "MP for Muar. MUDA President. Fighting for the rakyat."),
    ("twitter", "rafizi_ramli_x", "rafizi_ramli", "Rafizi Ramli", 980_000, True, 82.7,
     ["economy", "finance", "politics"], "positive",
     "Minister of Economy. Kerajaan Madani. Data-driven policymaker."),
    ("twitter", "nurul_izzah_x", "nurul_izzah", "Nurul Izzah Anwar", 1_100_000, True, 83.4,
     ["politics", "human_rights", "democracy"], "mixed",
     "MP Permatang Pauh. PKR VP. Daughter, mother, politician."),
    ("twitter", "malaysiakini_x", "malaysiakini", "Malaysiakini", 890_000, True, 79.8,
     ["news", "politics", "economy"], "neutral",
     "Malaysia's independent news source. Est. 1999."),
    ("twitter", "mkinieng_x", "mkinieng", "Malaysiakini English", 450_000, True, 74.1,
     ["news", "economy"], "neutral",
     "English news from Malaysiakini."),
    ("twitter", "shahril_hamdan", "shahril_hamdan", "Shahril Hamdan", 320_000, False, 65.3,
     ["economy", "finance"], "negative",
     "Economist. Former KWSP CEO. Commentator."),
    ("twitter", "zaid_ibrahim_x", "zaidbrahim", "Zaid Ibrahim", 540_000, False, 71.2,
     ["law", "politics"], "negative",
     "Lawyer. Former Minister. Plain-spoken."),
    # ── TikTok ─────────────────────────────────────────────────────────────────
    ("tiktok", "tktk_kawankita01", "kawankita.my", "Kawan Kita Malaysia", 2_400_000, False, 91.3,
     ["lifestyle", "cost_of_living", "food"], "negative",
     "Cerita rakyat biasa 🇲🇾 Konten viral tentang kehidupan seharian"),
    ("tiktok", "tktk_waniezurina", "waniezurina", "Wanie Zurina", 1_700_000, False, 87.6,
     ["food", "lifestyle", "viral"], "positive",
     "Masak jimat tapi sedap 🍳 #MasakJimat #FoodMY"),
    ("tiktok", "tktk_politikmalaysia", "politikmalaysia2024", "Politik Malaysia 2024", 3_100_000, True, 94.2,
     ["politics", "viral", "news"], "negative",
     "Berita & analisis politik terkini 🇲🇾 Verified creator"),
    ("tiktok", "tktk_komoditimas", "komoditi.mas", "Komoditi Malaysia", 890_000, False, 72.4,
     ["economy", "palm_oil", "agriculture"], "mixed",
     "Industri kelapa sawit & komoditi Malaysia 🌴"),
    # ── Facebook ────────────────────────────────────────────────────────────────
    ("facebook", "fb_mkini", "malaysiakini.fb", "Malaysiakini", 4_200_000, True, 88.9,
     ["news", "politics", "economy"], "neutral",
     "Malaysia's leading independent news portal."),
    ("facebook", "fb_sinchew", "sinchewdailynews", "Sin Chew Daily", 3_800_000, True, 86.1,
     ["news", "chinese_community", "economy"], "neutral",
     "马来西亚星洲日报 · Malaysia's largest Chinese newspaper."),
    ("facebook", "fb_harakah", "harakah.daily", "Harakah Daily", 1_900_000, False, 78.3,
     ["politics", "islamism"], "negative",
     "Akhbar parti PAS. Suara Islam dan Keadilan."),
    # ── News/RSS ─────────────────────────────────────────────────────────────────
    ("news", "bernama_rss", "bernama", "BERNAMA", 680_000, True, 77.5,
     ["national_news", "government"], "neutral",
     "Malaysia's National News Agency."),
    ("news", "thestar_rss", "thestar_my", "The Star Malaysia", 820_000, True, 80.2,
     ["news", "economy", "business"], "neutral",
     "Malaysia's leading English newspaper."),
    ("news", "fmtmalaysia_rss", "freemalaysiatoday", "Free Malaysia Today", 710_000, True, 79.1,
     ["news", "politics"], "negative",
     "Independent news and analysis."),
]


def seed_influencers() -> dict:
    rows = []
    imap = {}
    for (platform, uid_str, username, display_name, followers, verified,
         influence, topics, sentiment, bio) in INFLUENCERS_RAW:
        iid = uid()
        imap[username] = {"id": iid, "platform": platform, "platform_user_id": uid_str,
                          "followers": followers}
        rows.append({
            "id": iid,
            "platform": platform,
            "platform_user_id": uid_str,
            "username": username,
            "display_name": display_name,
            "bio": bio,
            "followers_count": followers,
            "following_count": rng.randint(200, 3000),
            "posts_count": rng.randint(500, 8000),
            "verified": verified,
            "influence_score": influence,
            "avg_engagement_rate": round(rng.uniform(1.5, 8.5), 2),
            "primary_language": "mixed",
            "primary_topics": topics,
            "sentiment_lean": sentiment,
            "is_monitored": True,
            "is_flagged": username in {"kawankita.my", "politikmalaysia2024"},
            "flag_reason": "High-volume coordinated narrative amplifier" if username in {"kawankita.my", "politikmalaysia2024"} else None,
            "last_active": ts(rng.uniform(0.1, 6)),
        })
    inserted = insert("influencers", rows, upsert_on="platform,platform_user_id")
    # Remap IDs from DB response
    for row in inserted:
        for username, info in imap.items():
            if info["platform_user_id"] == row.get("platform_user_id"):
                imap[username]["id"] = row["id"]
                break
    print(f"  Inserted {len(inserted)} influencers")
    return imap


# ═══════════════════════════════════════════════════════════════════════════════
#  2. NARRATIVES
# ═══════════════════════════════════════════════════════════════════════════════

NARRATIVES_RAW = [
    # (key, title, summary, status, threat, virality, sentiment_dist,
    #  hashtags, platforms, languages, coordinated, coord_score, momentum)
    (
        "subsidy",
        "Subsidi Petrol Dihapus — Kerajaan Didesak Balik Balik",
        "Warga negara marah dengan cadangan menghapuskan subsidi petrol RON95 dalam Belanjawan 2025. "
        "Perdebatan memuncak dengan dakwaan beban kos hidup semakin tinggi.",
        "active", 9, 87.4,
        {"positive": 42, "negative": 312, "neutral": 89, "mixed": 34},
        ["subsidipetrol", "bajetmalaysia2025", "ron95", "koshidup", "kerajaanmadani"],
        {"twitter": 180, "tiktok": 145, "facebook": 98, "news": 54},
        {"ms": 310, "en": 120, "mixed": 47},
        True, 0.74, 78.5,
    ),
    (
        "sawit",
        "EU Deforestation Law — Industri Sawit Malaysia Terancam",
        "Undang-undang alam sekitar Eropah yang mengharamkan import produk berkaitan penebangan hutan "
        "mengancam eksport minyak sawit Malaysia bernilai RM 100 bilion. Kerajaan dan MPOB mendesak semakan.",
        "emerging", 7, 71.2,
        {"positive": 28, "negative": 187, "neutral": 134, "mixed": 41},
        ["sawitmalaysia", "eudforestation", "minyaksawit", "eksportmalaysia", "mpob"],
        {"twitter": 102, "facebook": 118, "news": 93, "tiktok": 77},
        {"en": 198, "ms": 167, "mixed": 25},
        False, 0.21, 55.3,
    ),
    (
        "koshidup",
        "Harga Barang Dapur Naik — Rakyat Susah Nak Idup",
        "Harga beras, telur, ayam dan sayur meningkat 20-40% dalam masa 3 bulan. "
        "Hashtag #HargaNaikLagi menjadi trending, dipacu oleh video TikTok viral.",
        "active", 8, 82.6,
        {"positive": 18, "negative": 421, "neutral": 73, "mixed": 29},
        ["harganaikLagi", "koshidup", "berasmahal", "telurmahal", "inflasi"],
        {"tiktok": 198, "twitter": 134, "facebook": 112, "news": 41},
        {"ms": 387, "en": 68, "mixed": 30},
        True, 0.68, 91.2,
    ),
    (
        "ringgit",
        "Ringgit Jatuh ke Paras Paling Rendah Sejak 1998",
        "USD/MYR mencecah 4.78 — paras yang tidak pernah dilihat sejak Krisis Kewangan Asia 1997-98. "
        "Penganalisis mempersoalkan keberkesanan Bank Negara.",
        "active", 8, 79.3,
        {"positive": 15, "negative": 289, "neutral": 142, "mixed": 38},
        ["ringgitjatuh", "myr", "bankNegara", "ekonomimalaysia", "kewanganmalaysia"],
        {"twitter": 201, "facebook": 87, "news": 112, "tiktok": 44},
        {"en": 245, "ms": 178, "mixed": 21},
        False, 0.18, 62.1,
    ),
    (
        "anwar",
        "Anwar Ibrahim Dituduh Nepotisme Lantik Kroni Dalam MARA",
        "Pendedahan mengenai pelantikan individu berkaitan keluarga PM ke jawatan tinggi dalam MARA dan GLCs "
        "mencetuskan kemarahan orang ramai dan tuntutan semakan.",
        "emerging", 8, 75.8,
        {"positive": 29, "negative": 334, "neutral": 87, "mixed": 22},
        ["anwarkroni", "mara", "nepotisme", "kerajaanmadani", "PRU16"],
        {"twitter": 189, "tiktok": 221, "facebook": 143, "news": 62},
        {"ms": 398, "en": 147, "mixed": 70},
        True, 0.81, 84.7,
    ),
    (
        "banjir",
        "Banjir Teruk Johor — Mangsa Terbiar, Kerajaan Dikritik Lambat",
        "Banjir terbesar dalam 10 tahun di Johor Bahru meninggalkan 12,000 mangsa. "
        "Video dakwaan petugas menyelamat lewat tular di TikTok.",
        "active", 7, 68.9,
        {"positive": 31, "negative": 278, "neutral": 112, "mixed": 19},
        ["banjirjohor", "mangkubanjir", "jbflood", "kerajaanlambat", "malaysiabencana"],
        {"tiktok": 156, "twitter": 98, "facebook": 134, "news": 77},
        {"ms": 334, "en": 112, "mixed": 19},
        False, 0.29, 43.8,
    ),
    (
        "tiktok_masak",
        "#MasakJimat Challenge — Viral Konten Jimat Belanja Dapur",
        "Challenge viral TikTok memperlihatkan cara memasak untuk 4 orang dengan kurang RM 15 sehari "
        "menjadi fenomena — 180 juta views dalam seminggu, mencerminkan tekanan kos hidup.",
        "active", 4, 61.4,
        {"positive": 189, "negative": 34, "neutral": 98, "mixed": 41},
        ["masakjimat", "jimatbelanja", "tiktokmalaysia", "foodhack", "dapur"],
        {"tiktok": 289, "twitter": 45, "facebook": 67, "news": 22},
        {"ms": 312, "en": 67, "mixed": 44},
        False, 0.08, 22.3,
    ),
    (
        "gst",
        "GST Balik? — Debat Semula Cukai Selepas Cadangan Belanjawan",
        "Kenyataan Menteri Kewangan berhubung kajian semula sistem percukaian mencetuskan spekulasi "
        "pengembalian GST, mencetuskan reaksi hebat daripada rakyat.",
        "declining", 6, 54.1,
        {"positive": 44, "negative": 198, "neutral": 134, "mixed": 28},
        ["gstbalik", "sst", "cukai", "belanjawan", "ekonomimalaysia"],
        {"twitter": 134, "facebook": 112, "news": 98, "tiktok": 34},
        {"ms": 267, "en": 101, "mixed": 10},
        False, 0.12, -18.4,
    ),
    (
        "boikot",
        "Kempen Boikot McDonald's & Starbucks Semakin Besar",
        "Gerakan boikot produk Amerika Syarikat berkaitan konflik Gaza berterusan. "
        "Pendapatan McDonald's Malaysia turun 19%. Ramai beralih ke produk tempatan.",
        "active", 5, 63.7,
        {"positive": 67, "negative": 123, "neutral": 156, "mixed": 44},
        ["boikotMCD", "boikotStarbucks", "freegaza", "malaysiasolidariti", "beliproduklokal"],
        {"tiktok": 178, "facebook": 189, "twitter": 87, "news": 45},
        {"ms": 378, "en": 101, "mixed": 20},
        False, 0.23, 11.7,
    ),
    (
        "mh370",
        "MH370 — 10 Tahun Teori Konspirasi Kembali Tular",
        "Ulang tahun ke-10 kehilangan MH370 mencetuskan gelombang teori konspirasi baru di media sosial, "
        "termasuk dakwaan Kerajaan menyembunyikan maklumat.",
        "active", 5, 58.3,
        {"positive": 12, "negative": 89, "neutral": 201, "mixed": 67},
        ["mh370", "mh370konspirasi", "malaysia370", "missingplane", "malaysiaairlines"],
        {"twitter": 112, "tiktok": 134, "facebook": 98, "news": 67},
        {"en": 245, "ms": 178, "mixed": 66},
        True, 0.55, 34.9,
    ),
]


def seed_narratives() -> dict:
    rows = []
    nmap = {}
    for item in NARRATIVES_RAW:
        (key, title, summary, status, threat, virality,
         sent_dist, hashtags, platforms, languages,
         coordinated, coord_score, momentum) = item
        nid = uid()
        nmap[key] = nid
        post_count = sum(sent_dist.values())
        rows.append({
            "id": nid,
            "title": title,
            "summary": summary,
            "description": summary,
            "status": status,
            "key_themes": hashtags[:3],
            "key_hashtags": hashtags,
            "sentiment_distribution": sent_dist,
            "post_count": post_count,
            "unique_authors": rng.randint(int(post_count * 0.4), int(post_count * 0.85)),
            "engagement_total": round(rng.uniform(post_count * 12, post_count * 48), 1),
            "virality_score": virality,
            "threat_level": threat,
            "first_detected": ts(rng.uniform(6, 48)),
            "last_activity": ts(rng.uniform(0.05, 2)),
            "is_coordinated": coordinated,
            "coordination_score": coord_score,
            "coordination_signals": (
                ["burst_timing", "near_duplicate_content"] if coordinated else []
            ),
            "momentum_score": momentum,
            "languages": languages,
            "platforms": platforms,
        })
    inserted = insert("narratives", rows)
    # Re-map IDs if DB assigned different UUIDs
    for row in inserted:
        for key, nid in nmap.items():
            if nid == row.get("id"):
                nmap[key] = row["id"]
                break
    print(f"  Inserted {len(inserted)} narratives")
    return nmap


# ═══════════════════════════════════════════════════════════════════════════════
#  3. HASHTAGS  (upsert; triggers handle total_count via post_hashtags)
# ═══════════════════════════════════════════════════════════════════════════════

HASHTAG_COUNTS = {
    "subsidipetrol": 4_812, "bajetmalaysia2025": 3_991, "ron95": 2_344,
    "koshidup": 5_102, "kerajaanmadani": 3_211, "harganaikLagi": 6_788,
    "inflasi": 3_445, "berasmahal": 2_901, "telurmahal": 2_122,
    "sawitmalaysia": 2_876, "eudforestation": 1_654, "minyaksawit": 2_102,
    "eksportmalaysia": 1_243, "mpob": 987,
    "ringgitjatuh": 3_891, "myr": 2_454, "bankNegara": 1_879,
    "ekonomimalaysia": 2_987, "kewanganmalaysia": 1_122,
    "anwarkroni": 4_123, "mara": 1_934, "nepotisme": 2_789, "PRU16": 3_112,
    "banjirjohor": 3_445, "mangkubanjir": 2_112, "jbflood": 1_887,
    "kerajaanlambat": 2_001, "malaysiabencana": 1_334,
    "masakjimat": 7_234, "jimatbelanja": 4_512, "tiktokmalaysia": 6_001,
    "foodhack": 3_211, "dapur": 2_876,
    "gstbalik": 2_345, "sst": 1_765, "cukai": 1_432, "belanjawan": 2_098,
    "boikotMCD": 3_987, "boikotStarbucks": 2_765, "freegaza": 1_897,
    "malaysiasolidariti": 2_112, "beliproduklokal": 2_876,
    "mh370": 4_213, "mh370konspirasi": 2_109, "malaysia370": 1_998,
    "missingplane": 1_543, "malaysiaairlines": 1_312,
    "PRU15": 1_987, "malaysiamadani": 2_543, "politikmalaysia": 3_876,
}


def seed_hashtags() -> dict:
    rows = []
    hmap = {}
    for tag, count in HASHTAG_COUNTS.items():
        hid = uid()
        hmap[tag.lower()] = hid
        rows.append({
            "id": hid,
            "tag": tag.lower(),
            "total_count": count,
            "first_seen": ts(rng.uniform(12, 96)),
            "last_seen": ts(rng.uniform(0, 3)),
        })
    inserted = insert("hashtags", rows, upsert_on="tag")
    for row in inserted:
        hmap[row["tag"]] = row["id"]
    print(f"  Inserted/upserted {len(inserted)} hashtags")
    return hmap


# ═══════════════════════════════════════════════════════════════════════════════
#  4. ENTITIES
# ═══════════════════════════════════════════════════════════════════════════════

ENTITIES_RAW = [
    # (name, type, importance)
    ("Anwar Ibrahim", "PERSON", 92.4),
    ("Rafizi Ramli", "PERSON", 87.1),
    ("Khairy Jamaluddin", "PERSON", 84.3),
    ("Syed Saddiq", "PERSON", 81.2),
    ("Nurul Izzah Anwar", "PERSON", 78.9),
    ("Tengku Zafrul", "PERSON", 75.4),
    ("Fadhillah Yusof", "PERSON", 71.2),
    ("Bank Negara Malaysia", "ORG", 88.7),
    ("MARA", "ORG", 79.3),
    ("MPOB", "ORG", 72.1),
    ("Petronas", "ORG", 85.6),
    ("Malaysia Airlines", "ORG", 74.2),
    ("McDonald's Malaysia", "ORG", 67.8),
    ("Kerajaan Madani", "ORG", 91.2),
    ("PKR", "ORG", 83.4),
    ("UMNO", "ORG", 82.1),
    ("Kuala Lumpur", "LOCATION", 88.9),
    ("Johor Bahru", "LOCATION", 76.4),
    ("Putrajaya", "LOCATION", 84.1),
    ("Sabah", "LOCATION", 71.3),
    ("Penang", "LOCATION", 74.8),
    ("Palm Oil", "TOPIC", 82.3),
    ("Inflation", "TOPIC", 89.1),
    ("Subsidy Rationalisation", "TOPIC", 91.4),
    ("Budget 2025", "TOPIC", 87.6),
    ("Gaza Boycott", "TOPIC", 71.2),
    ("MH370", "TOPIC", 76.8),
    ("Ringgit Depreciation", "TOPIC", 84.9),
    ("GST", "TOPIC", 72.3),
    ("Flood Relief", "TOPIC", 68.4),
]


def seed_entities() -> dict:
    rows = []
    emap = {}
    for name, etype, importance in ENTITIES_RAW:
        eid = uid()
        emap[name] = eid
        rows.append({
            "id": eid,
            "name": name,
            "type": etype,
            "normalized_name": name.lower(),
            "importance_score": importance,
            "first_seen": ts(rng.uniform(12, 96)),
            "last_seen": ts(rng.uniform(0, 3)),
        })
    inserted = insert("entities", rows, upsert_on="normalized_name,type")
    for row in inserted:
        emap[row["name"]] = row["id"]
    print(f"  Inserted {len(inserted)} entities")
    return emap


# ═══════════════════════════════════════════════════════════════════════════════
#  5. POSTS
# ═══════════════════════════════════════════════════════════════════════════════

# (narrative_key, platform, lang, content, sentiment, score, likes, shares, comments, views,
#  author_username, author_followers, hashtags_used, entities_used, hours_ago)
POSTS_TEMPLATE = [
    # ── SUBSIDI PETROL ────────────────────────────────────────────────────────
    ("subsidy", "twitter", "ms",
     "Kerajaan nak hapus subsidi RON95??? Ini bermakna harga petrol naik 60 sen seliter. "
     "Dengan gaji RM1,500 macam mana nak survive? #SubsidiPetrol #KosHidup",
     "negative", -0.82, 3412, 1823, 891, 45000,
     "rafizi_ramli", 980_000, ["subsidipetrol", "koshidup"], ["Rafizi Ramli", "Subsidy Rationalisation"], 1.2),
    ("subsidy", "twitter", "en",
     "The subsidy rationalisation for RON95 is inevitable — Malaysia spends RM14bn/year on fuel subsidies. "
     "But the implementation matters. Targeted subsidies, please. #BudgetMalaysia2025 #KerajaanMadani",
     "mixed", -0.21, 2876, 1102, 543, 32000,
     "shahril_hamdan", 320_000, ["bajetmalaysia2025", "kerajaanmadani"], ["Budget 2025", "Subsidy Rationalisation"], 2.1),
    ("subsidy", "tiktok", "ms",
     "POV: Kau drive Grab, pakai petrol RON95. Kerajaan nak remove subsidi. "
     "Pendapatan kau RM70 sehari, minyak dah RM5 seliter. Macam mana nak survive?? "
     "#SubsidiPetrol #KosHidup #GrabMalaysia #KerajaanMadani",
     "negative", -0.91, 87432, 34219, 8921, 2_400_000,
     "kawankita.my", 2_400_000, ["subsidipetrol", "koshidup"], ["Subsidy Rationalisation", "Inflation"], 0.4),
    ("subsidy", "tiktok", "ms",
     "Gua dah kira. Kalau RON95 naik 60 sen, sebulan tambah RM180 untuk kereta Myvi. "
     "Tu belum kira barang lain yang naik. Rakyat mana tahan. Share kalau setuju! "
     "#SubsidiPetrol #HargaNaikLagi #Malaysia",
     "negative", -0.87, 54321, 28904, 6712, 1_800_000,
     "politikmalaysia2024", 3_100_000, ["subsidipetrol", "harganaikLagi"], ["Subsidy Rationalisation"], 0.8),
    ("subsidy", "facebook", "ms",
     "BREAKING: Menteri Ekonomi sahkan kajian semula subsidi RON95 akan dibentangkan dalam Belanjawan 2025. "
     "Mekanisme 'subsidi disasarkan' akan diperkenalkan menggunakan data MyKad. "
     "Apa pendapat anda? #BajetMalaysia2025",
     "negative", -0.43, 12876, 8901, 4321, 890_000,
     "malaysiakini.fb", 4_200_000, ["bajetmalaysia2025", "subsidipetrol"], ["Budget 2025", "Kerajaan Madani"], 3.5),
    ("subsidy", "news", "en",
     "RON95 Subsidy Phase-Out: What Analysts Say About the Impact on M40 Households. "
     "The proposed targeted subsidy mechanism could save RM8.5 billion annually, but experts warn "
     "of implementation challenges. Full analysis inside.",
     "negative", -0.38, 892, 1243, 287, 45000,
     "thestar_my", 820_000, ["subsidipetrol", "bajetmalaysia2025"], ["Subsidy Rationalisation", "Budget 2025", "Inflation"], 4.2),
    ("subsidy", "twitter", "ms",
     "Saya sokong penghapusan subsidi petrol DENGAN SYARAT: ada sistem pampasan yang benar2 adil. "
     "Bukan cara lama - letak duit terus dalam MyKasih, bukan barang. "
     "Rakyat mahu keadilan, bukan janji kosong. #KerajaanMadani #SubsidiPetrol",
     "mixed", 0.12, 1987, 876, 312, 28000,
     "syedsaddiq", 1_220_000, ["subsidipetrol", "kerajaanmadani"], ["Syed Saddiq", "Subsidy Rationalisation"], 5.1),
    ("subsidy", "twitter", "en",
     "Genuinely concerned about the timing of RON95 subsidy removal. Global commodity prices are still elevated, "
     "ringgit is weak, cost of living is at record high. Why now? #Malaysia #Economy",
     "negative", -0.71, 2341, 987, 432, 19000,
     "khairykj", 1_850_000, ["koshidup", "ekonomimalaysia"], ["Khairy Jamaluddin", "Inflation"], 6.3),
    ("subsidy", "tiktok", "ms",
     "Mak ai!! Baru tau rupanya Malaysia habiskan RM14 BILION setahun untuk subsidi petrol je. "
     "Kalau duit tu untuk pendidikan & hospital lagi best kan? Tapi kenapa rakyat yg kena tanggung? "
     "#SubsidiPetrol #Malaysia #politik",
     "mixed", -0.24, 34521, 18234, 4312, 980_000,
     "waniezurina", 1_700_000, ["subsidipetrol", "kerajaanmadani"], ["Subsidy Rationalisation"], 7.8),
    ("subsidy", "facebook", "ms",
     "Kepada semua yang setuju subsidi petrol perlu diteruskan — LIKE. "
     "Kepada yang sokong penghapusan subsidi — KOMEN. "
     "Mari kita tengok apa majoriti rakyat Malaysia nak. #Subsidi #Malaysia",
     "neutral", -0.05, 45123, 12309, 9821, 340_000,
     "harakah.daily", 1_900_000, ["subsidipetrol", "bajetmalaysia2025"], ["Subsidy Rationalisation"], 8.9),

    # ── SAWIT / PALM OIL ──────────────────────────────────────────────────────
    ("sawit", "twitter", "en",
     "EU's deforestation regulation will effectively block palm oil from Malaysia. "
     "This targets an industry that supports 650,000 smallholders. Where's the fairness? "
     "#PalmOil #MalaysiaPalmOil #EU",
     "negative", -0.76, 3212, 1654, 543, 34000,
     "mkinieng", 450_000, ["sawitmalaysia", "eudforestation"], ["Palm Oil", "MPOB"], 2.3),
    ("sawit", "facebook", "en",
     "MPOB CEO: Malaysia will file formal complaint to WTO over EU deforestation regulation. "
     "'This is protectionism disguised as environmentalism,' he says. "
     "Full statement in comments. #PalmOil #MPOB",
     "negative", -0.54, 8765, 4321, 1876, 78000,
     "malaysiakini.fb", 4_200_000, ["sawitmalaysia", "mpob"], ["MPOB", "Palm Oil"], 1.8),
    ("sawit", "tiktok", "ms",
     "Tahu tak? Ladang sawit Malaysia LAGI baik dari segi alam sekitar berbanding EU claims. "
     "Kami ada RSPO certification! EU ni bias. Sokong petani sawit Malaysia 🌴 "
     "#SawitMalaysia #PalmOil #EURegulation",
     "negative", -0.68, 23456, 12345, 3456, 567000,
     "komoditi.mas", 890_000, ["sawitmalaysia", "eudforestation", "mpob"], ["Palm Oil", "MPOB"], 3.4),
    ("sawit", "news", "en",
     "Malaysia's Palm Oil Exports at Risk: EU Deforestation Regulation Could Cost RM9.2 Billion Annually. "
     "Trade minister to hold emergency meeting with plantation sector stakeholders next week.",
     "negative", -0.67, 456, 789, 123, 23000,
     "bernama", 680_000, ["sawitmalaysia", "eksportmalaysia"], ["Palm Oil", "MPOB", "Kuala Lumpur"], 4.1),
    ("sawit", "twitter", "ms",
     "Pekerja ladang sawit di Sabah dan Sarawak yang akan paling terkesan dengan embargo EU. "
     "Bukan CEO syarikat besar. Rakyat biasa yang bergantung pada industri ini. "
     "#SawitMalaysia #EUDeforestation #Sabah",
     "negative", -0.81, 1876, 987, 321, 14000,
     "nurul_izzah", 1_100_000, ["sawitmalaysia", "eksportmalaysia"], ["Nurul Izzah Anwar", "Sabah", "Palm Oil"], 5.7),

    # ── KOS HIDUP ─────────────────────────────────────────────────────────────
    ("koshidup", "tiktok", "ms",
     "Challenge #MasakJimat tapi realiti 2024: daging ayam RM13/kg, beras RM30/10kg, telur RM15/30biji. "
     "Cuba masak untuk 4 orang dengan RM15 sekarang. MUSTAHIL. #HargaNaikLagi #KosHidup",
     "negative", -0.93, 124567, 67890, 23456, 4_500_000,
     "kawankita.my", 2_400_000, ["harganaikLagi", "koshidup", "berasmahal", "telurmahal"],
     ["Inflation", "Subsidy Rationalisation"], 0.3),
    ("koshidup", "tiktok", "ms",
     "Bukan nak drama tapi betul - hari ni pergi pasar, beli barang untuk seminggu: RM287. "
     "Tahun lepas sama barang RM198. Naik 45%. Gaji naik? 3%. Tolong explain macam mana nak cope. "
     "#HargaNaikLagi #Inflasi #MalaysiaEkonomi",
     "negative", -0.88, 98765, 45678, 18923, 3_200_000,
     "waniezurina", 1_700_000, ["harganaikLagi", "inflasi", "koshidup"],
     ["Inflation"], 1.1),
    ("koshidup", "twitter", "ms",
     "Indeks Harga Pengguna Malaysia naik 3.8% YoY Ogos 2024 - tertinggi dalam 2 tahun. "
     "Makanan & minuman bukan alkohol +5.4%. Pengangkutan +4.1%. "
     "Data: DOSM. #Inflasi #KosHidup #EkonomiMalaysia",
     "negative", -0.61, 4312, 2134, 876, 45000,
     "rafizi_ramli", 980_000, ["inflasi", "koshidup", "ekonomimalaysia"],
     ["Rafizi Ramli", "Inflation", "Kuala Lumpur"], 2.4),
    ("koshidup", "facebook", "ms",
     "TANGKAPAN: Harga ayam di pasar AEON Wangsa Maju - RM16.90/kg. Harga tol naik. "
     "Harga diesel naik. Harga gas naik. Tapi PM cakap ekonomi Malaysia 'on track'. "
     "ON TRACK KE MANA??? #HargaNaikLagi",
     "negative", -0.95, 23456, 18765, 7654, 234000,
     "harakah.daily", 1_900_000, ["harganaikLagi", "koshidup"], ["Anwar Ibrahim", "Inflation"], 3.2),
    ("koshidup", "news", "ms",
     "Harga Beras Tempatan Naik 22% — BERNAS Umum Masalah Bekalan Akibat Cuaca Panas. "
     "Kerajaan pertimbangkan import beras segera dari Vietnam dan Thailand untuk stabilkan pasaran.",
     "negative", -0.72, 1234, 2345, 678, 56000,
     "freemalaysiatoday", 710_000, ["berasmahal", "koshidup"], ["Inflation", "Kuala Lumpur"], 4.8),
    ("koshidup", "twitter", "en",
     "Malaysian household debt-to-GDP at 84% - one of highest in Asia. Now subsidy removal on top of "
     "inflation. The squeeze on middle-income families is real and the data backs it up. #MalaysiaEconomy",
     "negative", -0.79, 3123, 1567, 543, 27000,
     "shahril_hamdan", 320_000, ["koshidup", "inflasi", "ekonomimalaysia"],
     ["Inflation", "Bank Negara Malaysia"], 6.1),
    ("koshidup", "tiktok", "ms",
     "My mom cried at the supermarket today because she couldn't afford the groceries she used to buy. "
     "She worked her whole life and now... this is Malaysia 2024. "
     "#KosHidup #MalaysiaEconomy #Sedih",
     "negative", -0.97, 187654, 89234, 34521, 6_700_000,
     "kawankita.my", 2_400_000, ["koshidup", "harganaikLagi"], ["Inflation"], 0.9),

    # ── RINGGIT ───────────────────────────────────────────────────────────────
    ("ringgit", "twitter", "en",
     "USD/MYR just hit 4.79. I've been an economist for 20 years and this is the weakest ringgit "
     "since the Asian Financial Crisis. BNM needs to act NOW. #RinggitJatuh #MYR #Malaysia",
     "negative", -0.84, 5678, 3456, 1234, 56000,
     "shahril_hamdan", 320_000, ["ringgitjatuh", "myr", "bankNegara"],
     ["Ringgit Depreciation", "Bank Negara Malaysia"], 1.4),
    ("ringgit", "twitter", "ms",
     "Bila ringgit jatuh, semua barang import naik — laptop, kereta, ubat. "
     "Tak perlu 'ekonomist' untuk faham kesan ini kepada rakyat biasa. "
     "BNM tolong buat sesuatu. #RinggitJatuh #EkonomiMalaysia",
     "negative", -0.78, 4321, 2109, 876, 38000,
     "syedsaddiq", 1_220_000, ["ringgitjatuh", "bankNegara", "ekonomimalaysia"],
     ["Syed Saddiq", "Ringgit Depreciation", "Bank Negara Malaysia"], 2.8),
    ("ringgit", "facebook", "en",
     "Ringgit depreciation explained: Why it's happening and what it means for your wallet. "
     "From imported goods to your children's overseas education — the full impact analysis.",
     "negative", -0.45, 9876, 5432, 2345, 123000,
     "malaysiakini.fb", 4_200_000, ["ringgitjatuh", "myr"],
     ["Ringgit Depreciation", "Bank Negara Malaysia", "Kuala Lumpur"], 3.3),
    ("ringgit", "news", "en",
     "BNM Governor: Ringgit Weakness Reflects Global Dollar Strength, Not Malaysia-Specific Factors. "
     "Central bank has adequate reserves to intervene if necessary, governor reassures markets.",
     "neutral", 0.08, 765, 1234, 234, 34000,
     "bernama", 680_000, ["ringgitjatuh", "bankNegara", "myr"],
     ["Bank Negara Malaysia", "Ringgit Depreciation"], 5.6),
    ("ringgit", "twitter", "en",
     "Thread 🧵: Why the ringgit is falling and what the government can/can't do about it. "
     "1/ The main driver is USD strength — Fed rates staying higher for longer. Not unique to Malaysia... "
     "#RinggitJatuh #Malaysia #Economics",
     "neutral", 0.12, 6789, 4567, 1876, 87000,
     "shahril_hamdan", 320_000, ["ringgitjatuh", "myr", "ekonomimalaysia"],
     ["Ringgit Depreciation", "Bank Negara Malaysia"], 4.2),

    # ── ANWAR / NEPOTISME ─────────────────────────────────────────────────────
    ("anwar", "twitter", "ms",
     "Dokumen bocor tunjuk 3 ahli keluarga PM Anwar dilantik ke jawatan dalam GLCs 6 bulan lepas. "
     "Ini yang dimaksudkan oleh rakyat bila cakap soal nepotisme. "
     "@AnwarIbrahim tolong jelaskan. #AnwarKroni #Nepotisme",
     "negative", -0.91, 8765, 5432, 2109, 98000,
     "syedsaddiq", 1_220_000, ["anwarkroni", "mara", "nepotisme"],
     ["Anwar Ibrahim", "Syed Saddiq", "MARA", "Kerajaan Madani"], 1.5),
    ("anwar", "tiktok", "ms",
     "VIRAL: Senarai nama ahli keluarga PM yang dapat jawatan kerajaan. "
     "Saya ada dokumen. Tonton sampai habis. Like & share sebelum dipadam! "
     "#AnwarKroni #Nepotisme #KerajaanMadani #PRU16",
     "negative", -0.94, 234567, 123456, 45678, 8_900_000,
     "politikmalaysia2024", 3_100_000, ["anwarkroni", "nepotisme", "PRU16"],
     ["Anwar Ibrahim", "MARA"], 0.5),
    ("anwar", "twitter", "ms",
     "Tuduhan nepotisme terhadap PM perlu disiasat secara telus dan bebas. "
     "Jika benar, ia menghancurkan kepercayaan rakyat terhadap Kerajaan Madani. "
     "Saya menunggu penjelasan rasmi. #KerajaanMadani",
     "negative", -0.71, 3456, 1876, 654, 34000,
     "nurul_izzah", 1_100_000, ["anwarkroni", "kerajaanmadani"],
     ["Nurul Izzah Anwar", "Anwar Ibrahim", "Kerajaan Madani"], 3.1),
    ("anwar", "tiktok", "ms",
     "Korang tahu tak kalau PM Malaysia duduk dalam 'Hall of Shame' Nepotisme Asia? "
     "Apa yang kerajaan buat pasal ni? Kita boleh buat sesuatu di PRU16! "
     "#AnwarKroni #PRU16 #MalaysiaBoleh",
     "negative", -0.88, 98765, 54321, 19876, 3_450_000,
     "kawankita.my", 2_400_000, ["anwarkroni", "nepotisme", "PRU16"],
     ["Anwar Ibrahim"], 1.2),

    # ── BANJIR ────────────────────────────────────────────────────────────────
    ("banjir", "tiktok", "ms",
     "Kawasan Kempas Baru JB masih dalam air paras dada. Dah 3 hari. Mana Bomba? "
     "Mana wakil rakyat? Datang ambil gambar je tapi takde bantuan. "
     "#BanjirJohor #Mangkubanjir #JBFlood",
     "negative", -0.93, 87654, 43212, 18765, 2_800_000,
     "kawankita.my", 2_400_000, ["banjirjohor", "mangkubanjir", "jbflood"],
     ["Johor Bahru", "Flood Relief"], 2.1),
    ("banjir", "twitter", "ms",
     "Gambar semasa: Jalan Skudai masih ditenggelami air. Hampir 15,000 mangsa banjir di Johor. "
     "Pihak berkuasa minta mangsa bersabar. 'Bersabar' ke arah mana?? "
     "#BanjirJohor #Johor #MangsaBanjir",
     "negative", -0.87, 5678, 3456, 1234, 45000,
     "malaysiakini", 890_000, ["banjirjohor", "mangkubanjir"], ["Johor Bahru", "Flood Relief"], 3.4),
    ("banjir", "news", "ms",
     "Banjir Johor: Kerajaan Negeri Isytihar Bencana Alam — 14,200 Mangsa Dipindahkan ke PPS. "
     "Bantuan segera RM1,000 per keluarga diumumkan oleh PM.",
     "neutral", -0.12, 2345, 3456, 987, 67000,
     "bernama", 680_000, ["banjirjohor", "mangkubanjir"], ["Johor Bahru", "Anwar Ibrahim", "Flood Relief"], 4.7),

    # ── MASAKJIMAT / TIKTOK VIRAL ─────────────────────────────────────────────
    ("tiktok_masak", "tiktok", "ms",
     "Day 30 of #MasakJimat challenge! Hari ni buat Ayam Goreng Kunyit dengan nasi & sayur untuk "
     "4 orang = RM12.50 je! Cara jimat tapi sedap. Full recipe di bawah 👇 "
     "#MasakJimat #JimatBelanja #TikTokMalaysia",
     "positive", 0.87, 345678, 187654, 67890, 12_000_000,
     "waniezurina", 1_700_000, ["masakjimat", "jimatbelanja", "tiktokmalaysia", "dapur"],
     ["Inflation"], 0.2),
    ("tiktok_masak", "tiktok", "ms",
     "Reaksi mak saya bila tunjuk cara masak jimat #MasakJimat 😭 Dia pun terkejut boleh jimat sampai "
     "RM200 sebulan! Try method ni korang semua. Recipe percuma dalam bio. "
     "#MasakJimat #FoodHack #TikTokMY",
     "positive", 0.91, 234567, 123456, 45678, 8_900_000,
     "waniezurina", 1_700_000, ["masakjimat", "foodhack", "tiktokmalaysia"],
     ["Inflation"], 1.3),
    ("tiktok_masak", "twitter", "ms",
     "Trend #MasakJimat di TikTok ini bukan sekadar viral - ia cerminan realiti kos hidup tinggi. "
     "Bila rakyat perlu belajar 'food hack' untuk survive, sesuatu sudah tidak kena. "
     "#KosHidup #MasakJimat",
     "mixed", -0.31, 2345, 1234, 456, 28000,
     "syedsaddiq", 1_220_000, ["masakjimat", "koshidup"], ["Inflation", "Syed Saddiq"], 2.8),

    # ── RINGGIT (more) ────────────────────────────────────────────────────────
    ("ringgit", "tiktok", "ms",
     "Ringgit jatuh = laptop gaming makin mahal 😭 Dulu RM3,200 sekarang RM4,100 untuk model yang sama. "
     "Tengah kumpul duit nak beli, tapi harga naik lagi. Malaysia kenapa? "
     "#RinggitJatuh #MYR #TechMalaysia",
     "negative", -0.82, 45678, 23456, 8765, 1_200_000,
     "politikmalaysia2024", 3_100_000, ["ringgitjatuh", "myr"],
     ["Ringgit Depreciation"], 2.7),

    # ── GST ───────────────────────────────────────────────────────────────────
    ("gst", "twitter", "ms",
     "Kalau GST balik semula, rakyat M40 yang paling teruk kena. SST lebih baik walaupun "
     "hasilnya kurang. Tolong jangan ulang kesilapan sama. #GSTBalik #Cukai #Malaysia",
     "negative", -0.73, 2987, 1543, 621, 25000,
     "shahril_hamdan", 320_000, ["gstbalik", "sst", "cukai"],
     ["GST", "Inflation"], 8.3),
    ("gst", "facebook", "en",
     "Finance Minister clarifies: GST reimplementation not on the table for Budget 2025. "
     "'We are looking at improving SST efficiency, not reverting to GST,' he tells Parliament.",
     "neutral", 0.15, 4567, 2345, 876, 67000,
     "malaysiakini.fb", 4_200_000, ["gstbalik", "belanjawan"], ["Budget 2025", "GST"], 6.4),

    # ── BOIKOT ────────────────────────────────────────────────────────────────
    ("boikot", "tiktok", "ms",
     "Selepas 8 bulan boikot, McDonald's Malaysia rugi RM400 juta. Ini KUASA rakyat! "
     "Jangan stop sekarang. Teruskan sokong produk tempatan. "
     "#BoikotMCD #FreePalestine #BuyMalaysia",
     "negative", -0.71, 123456, 67890, 23456, 4_500_000,
     "politikmalaysia2024", 3_100_000, ["boikotMCD", "freegaza", "beliproduklokal"],
     ["McDonald's Malaysia", "Gaza Boycott"], 1.6),
    ("boikot", "facebook", "ms",
     "UPDATE BOIKOT: McDonald's Malaysia tutup 48 cawangan. Pendapatan -19% Q3 2024. "
     "Ini bukan tentang burger - ini tentang prinsip. Terima kasih semua yg menyokong. "
     "#BoikotMCD #MalaysiaSolidariti",
     "positive", 0.34, 34567, 23456, 9876, 456000,
     "harakah.daily", 1_900_000, ["boikotMCD", "malaysiasolidariti"],
     ["McDonald's Malaysia", "Gaza Boycott"], 3.8),

    # ── MH370 ─────────────────────────────────────────────────────────────────
    ("mh370", "tiktok", "ms",
     "10 tahun berlalu tapi keluarga MH370 masih tak dapat jawapan. "
     "Video saya ini dapat hampir 2 juta views sebab rakyat masih tanya: "
     "APA YANG KERAJAAN SEMBUNYIKAN? #MH370 #MH370Konspirasi #MissingPlane",
     "negative", -0.79, 67890, 34512, 12345, 2_100_000,
     "politikmalaysia2024", 3_100_000, ["mh370", "mh370konspirasi", "missingplane"],
     ["MH370", "Malaysia Airlines", "Anwar Ibrahim"], 1.9),
    ("mh370", "twitter", "en",
     "MH370 families deserve closure, not conspiracy theories. The Ocean Infinity search continues. "
     "Please stop the misinformation — it adds to the families' pain. "
     "#MH370 #Malaysia370",
     "negative", -0.43, 3456, 1678, 543, 34000,
     "nurul_izzah", 1_100_000, ["mh370", "malaysia370"], ["MH370", "Malaysia Airlines"], 4.3),
    ("mh370", "news", "en",
     "MH370: Tenth Anniversary — New Documentary Claims Classified Radar Data Was Withheld. "
     "Malaysian Government Denies Allegations, Calls Accusations 'Baseless and Harmful'.",
     "negative", -0.52, 876, 1543, 345, 45000,
     "freemalaysiatoday", 710_000, ["mh370", "mh370konspirasi"], ["MH370", "Malaysia Airlines", "Kuala Lumpur"], 5.1),
]

# Additional high-volume posts to pad metrics to realistic daily totals
EXTRA_POSTS = [
    # Twitter general political chatter
    ("subsidy", "twitter", "ms",
     "Betul ke kerajaan nak kasi bantuan RM500 kepada isi rumah yang layak bila subsidi RON95 ditarik? "
     "Kena tengok syarat dulu. Harap ia sampai pada yang benar-benar perlukan.",
     "mixed", -0.15, 890, 432, 121, 8700,
     "khairykj", 1_850_000, ["subsidipetrol", "bajetmalaysia2025"], ["Khairy Jamaluddin"], 9.4),
    ("koshidup", "twitter", "en",
     "Real wages in Malaysia have been stagnant for a decade while housing, food and transport costs "
     "keep rising. When will Budget 2025 address this structural issue? #KosHidup #MalaysiaEconomy",
     "negative", -0.68, 1234, 678, 234, 12000,
     "shahril_hamdan", 320_000, ["koshidup", "inflasi"], ["Inflation", "Budget 2025"], 10.1),
    ("anwar", "facebook", "ms",
     "Kerajaan Madani yang diharapkan rakyat untuk lawan nepotisme kini dituduh nepotisme sendiri. "
     "Ironi yang menyedihkan. Rakyat layak mendapat lebih baik.",
     "negative", -0.82, 12345, 7654, 3210, 234000,
     "malaysiakini.fb", 4_200_000, ["anwarkroni", "kerajaanmadani"], ["Anwar Ibrahim", "Kerajaan Madani"], 7.2),
    ("ringgit", "twitter", "en",
     "The ringgit weakness isn't just a number on a screen — it's higher prices for imported food, "
     "medicine and electronics. Direct real-world impact on every Malaysian family.",
     "negative", -0.72, 2109, 1234, 456, 19000,
     "khairykj", 1_850_000, ["ringgitjatuh", "ekonomimalaysia"], ["Ringgit Depreciation", "Khairy Jamaluddin"], 11.3),
    ("boikot", "tiktok", "ms",
     "Tak sangka movement boikot boleh ada impak sebesar ni! Produk tempatan makin popular. "
     "Syarikat F&B Malaysia catat jualan rekod. Ini patut jadi normaliti! "
     "#BelliProdukLokal #BoikotMCD",
     "positive", 0.78, 56789, 34512, 12345, 1_890_000,
     "waniezurina", 1_700_000, ["boikotMCD", "beliproduklokal"], ["Gaza Boycott"], 5.9),
    ("sawit", "twitter", "en",
     "Thread on EU-MY palm oil dispute: Both sides have legitimate arguments. "
     "But the real losers will be 650k smallholders if we can't find a diplomatic solution.",
     "neutral", 0.08, 1876, 987, 321, 14000,
     "mkinieng", 450_000, ["sawitmalaysia", "eudforestation"], ["Palm Oil", "MPOB"], 13.2),
    ("banjir", "twitter", "ms",
     "JKM sahkan 14,312 mangsa banjir di Johor dalam 12 PPS. Bekalan makanan, air dan ubatan mencukupi. "
     "Operasi masih berjalan. #BanjirJohor",
     "neutral", 0.05, 3456, 1876, 543, 34000,
     "bernama", 680_000, ["banjirjohor"], ["Flood Relief", "Johor Bahru"], 6.8),
    ("tiktok_masak", "tiktok", "ms",
     "Ramai tanya macam mana nak jimat belanja dapur. Jawapan saya: meal plan + beli borong + masak sendiri. "
     "Boleh jimat sampai 40%! #MasakJimat #JimatBelanja",
     "positive", 0.82, 78965, 45678, 17654, 2_340_000,
     "waniezurina", 1_700_000, ["masakjimat", "jimatbelanja"], ["Inflation"], 3.6),
]

ALL_POSTS = POSTS_TEMPLATE + EXTRA_POSTS


def seed_posts(nmap: dict, imap: dict, hmap: dict, emap: dict):
    post_rows = []
    ph_rows = []  # post_hashtags
    pe_rows = []  # post_entities
    pn_rows = []  # post_narratives

    for item in ALL_POSTS:
        (nar_key, platform, lang, content, sentiment, sent_score,
         likes, shares, comments, views, author_username, author_followers,
         hashtag_keys, entity_keys, hours_ago) = item

        pid = uid()
        # Add ±20% noise to engagement numbers
        noise = lambda n: max(0, int(n * rng.uniform(0.8, 1.2)))
        l, s, c, v = noise(likes), noise(shares), noise(comments), noise(views)

        inf = imap.get(author_username)
        author_id = inf["platform_user_id"] if inf else author_username

        post_rows.append({
            "id": pid,
            "external_id": f"seed_{pid[:8]}",
            "platform": platform,
            "content": content,
            "content_normalized": content.lower(),
            "author_id": author_id,
            "author_username": author_username,
            "author_display_name": next(
                (r[3] for r in INFLUENCERS_RAW if r[2] == author_username), author_username
            ),
            "author_followers": author_followers,
            "author_verified": next(
                (r[5] for r in INFLUENCERS_RAW if r[2] == author_username), False
            ),
            "language": lang,
            "sentiment": sentiment,
            "sentiment_score": sent_score + rng.uniform(-0.05, 0.05),
            "engagement_score": eng(l, s, c, author_followers),
            "likes_count": l,
            "shares_count": s,
            "comments_count": c,
            "views_count": v,
            "is_repost": False,
            "posted_at": ts(hours_ago + rng.uniform(0, 0.5)),
            "processed_at": ts(hours_ago - 0.05),
            "metadata": {"seed": True},
        })

        # narrative assignment
        nar_id = nmap.get(nar_key)
        if nar_id:
            pn_rows.append({
                "post_id": pid,
                "narrative_id": nar_id,
                "similarity_score": round(rng.uniform(0.75, 0.98), 4),
                "assigned_at": ts(hours_ago - 0.01),
            })

        # hashtags
        for htag in hashtag_keys:
            hid = hmap.get(htag.lower())
            if hid:
                ph_rows.append({"post_id": pid, "hashtag_id": hid})

        # entities
        for ename in entity_keys:
            eid = emap.get(ename)
            if eid:
                pe_rows.append({
                    "post_id": pid,
                    "entity_id": eid,
                    "confidence": round(rng.uniform(0.75, 0.99), 3),
                })

    inserted_posts = insert("posts", post_rows)
    print(f"  Inserted {len(inserted_posts)} posts")

    # Disable trigger temporarily by inserting without it? No — just insert and let trigger run.
    inserted_ph = insert("post_hashtags", ph_rows, upsert_on="post_id,hashtag_id")
    print(f"  Inserted {len(inserted_ph)} post_hashtag rows")

    inserted_pe = insert("post_entities", pe_rows)
    print(f"  Inserted {len(inserted_pe)} post_entity rows")

    inserted_pn = insert("post_narratives", pn_rows, upsert_on="post_id,narrative_id")
    print(f"  Inserted {len(inserted_pn)} post_narrative rows")

    return inserted_posts


# ═══════════════════════════════════════════════════════════════════════════════
#  6. NARRATIVE TIMELINE  (48h hourly buckets per narrative)
# ═══════════════════════════════════════════════════════════════════════════════

def seed_narrative_timeline(nmap: dict):
    rows = []
    # Each narrative gets a 48-bucket timeline. Shape depends on status.
    shapes = {
        "subsidy":    "rising",
        "sawit":      "spike_recent",
        "koshidup":   "surge",
        "ringgit":    "rising",
        "anwar":      "spike_recent",
        "banjir":     "pulse",
        "tiktok_masak": "spike_early",
        "gst":        "declining",
        "boikot":     "stable",
        "mh370":      "spike_recent",
    }
    for key, nid in nmap.items():
        shape = shapes.get(key, "stable")
        for h in range(47, -1, -1):  # 47h ago → 0h ago
            base = 4
            frac = (47 - h) / 47  # 0→1 over time
            if shape == "rising":
                vol = max(1, int(base + frac * 22 + rng.gauss(0, 2)))
            elif shape == "surge":
                vol = max(1, int(base + frac * 35 + rng.gauss(0, 3)))
            elif shape == "spike_recent":
                vol = max(1, int(base + (frac ** 3) * 45 + rng.gauss(0, 2)))
            elif shape == "spike_early":
                peak_frac = 0.6
                vol = max(1, int(base + max(0, 1 - abs(frac - peak_frac) * 4) * 40 + rng.gauss(0, 2)))
            elif shape == "pulse":
                vol = max(1, int(base + math.sin(frac * math.pi * 2) * 12 + rng.gauss(0, 2)))
            elif shape == "declining":
                vol = max(1, int(base + (1 - frac) * 20 + rng.gauss(0, 2)))
            else:
                vol = max(1, int(base + rng.gauss(0, 2)))

            bucket_dt = NOW - timedelta(hours=h)
            bucket_dt = bucket_dt.replace(minute=0, second=0, microsecond=0)
            rows.append({
                "narrative_id": nid,
                "bucket": bucket_dt.isoformat(),
                "post_count": vol,
                "new_authors": max(1, int(vol * rng.uniform(0.4, 0.8))),
                "engagement": round(vol * rng.uniform(80, 400), 1),
                "sentiment_score": round(rng.uniform(-0.9, -0.1), 3),
            })

    inserted = insert("narrative_timeline", rows, upsert_on="narrative_id,bucket")
    print(f"  Inserted {len(inserted)} narrative_timeline rows")


# ═══════════════════════════════════════════════════════════════════════════════
#  7. HASHTAG TRENDS (24h hourly buckets)
# ═══════════════════════════════════════════════════════════════════════════════

def seed_hashtag_trends(hmap: dict):
    rows = []
    top_tags = list(HASHTAG_COUNTS.items())[:20]  # top 20 only
    for tag, total in top_tags:
        hid = hmap.get(tag.lower())
        if not hid:
            continue
        for h in range(23, -1, -1):
            bucket_dt = NOW - timedelta(hours=h)
            bucket_dt = bucket_dt.replace(minute=0, second=0, microsecond=0)
            hourly = max(1, int(total / 24 * rng.uniform(0.5, 2.5)))
            neg = int(hourly * rng.uniform(0.3, 0.6))
            pos = int(hourly * rng.uniform(0.05, 0.2))
            neu = max(0, hourly - neg - pos)
            rows.append({
                "hashtag_id": hid,
                "bucket": bucket_dt.isoformat(),
                "count": hourly,
                "sentiment_positive": pos,
                "sentiment_negative": neg,
                "sentiment_neutral": neu,
                "engagement_total": round(hourly * rng.uniform(100, 500), 1),
            })
    inserted = insert("hashtag_trends", rows, upsert_on="hashtag_id,bucket")
    print(f"  Inserted {len(inserted)} hashtag_trend rows")


# ═══════════════════════════════════════════════════════════════════════════════
#  8. ALERTS
# ═══════════════════════════════════════════════════════════════════════════════

def seed_alerts(nmap: dict):
    alerts = [
        {
            "id": uid(),
            "title": "KRITIKAL: Lonjakan Viral — Subsidi Petrol RON95 (3× Kadar Normal)",
            "description": "3,412 posts dalam 60 minit — 3.2× lebih tinggi dari baseline. "
                           "Sentimen negatif: 82%. 12 influencer besar turut serta. "
                           "Tanda koordinasi terkesan.",
            "severity": "critical",
            "status": "active",
            "alert_type": "narrative_spike",
            "source_id": nmap.get("subsidy"),
            "source_type": "narrative",
            "trigger_data": {
                "current_rate": 3412, "baseline_rate": 1067,
                "multiplier": 3.2, "negative_pct": 0.82,
                "narrative_key": "subsidy",
            },
            "affected_platforms": ["tiktok", "twitter", "facebook"],
            "affected_languages": ["ms", "en"],
            "post_count": 477,
            "reach_estimate": 14_200_000,
            "created_at": ts(0.3),
        },
        {
            "id": uid(),
            "title": "TINGGI: Tingkah Laku Terkoordinasi — Kempen Anti-Anwar",
            "description": "81% koordinasi score. 3 akaun besar hantar kandungan hampir serupa dalam 30 minit. "
                           "Kemungkinan serangan terancang. Tanda: burst_timing, near_duplicate_content.",
            "severity": "high",
            "status": "active",
            "alert_type": "coordinated_behavior",
            "source_id": nmap.get("anwar"),
            "source_type": "narrative",
            "trigger_data": {
                "coordination_score": 0.81,
                "signals": ["burst_timing", "near_duplicate_content"],
                "top_accounts": ["politikmalaysia2024", "kawankita.my"],
            },
            "affected_platforms": ["tiktok", "twitter"],
            "affected_languages": ["ms"],
            "post_count": 615,
            "reach_estimate": 9_800_000,
            "created_at": ts(1.1),
        },
        {
            "id": uid(),
            "title": "KRITIKAL: Sentimen Negatif Melampau — Kos Hidup (97% Negatif)",
            "description": "Sentimen negatif melonjak daripada 61% kepada 97% dalam 2 jam untuk "
                           "isu kos hidup. Video TikTok 'mak menangis di pasar' dengan 6.7M tayangan "
                           "mencetuskan gelombang amarah.",
            "severity": "critical",
            "status": "active",
            "alert_type": "sentiment_shift",
            "source_id": nmap.get("koshidup"),
            "source_type": "narrative",
            "trigger_data": {
                "previous_negative_pct": 0.61,
                "current_negative_pct": 0.97,
                "delta": 0.36,
                "trigger_post_views": 6_700_000,
            },
            "affected_platforms": ["tiktok", "facebook"],
            "affected_languages": ["ms"],
            "post_count": 541,
            "reach_estimate": 18_400_000,
            "created_at": ts(0.8),
        },
        {
            "id": uid(),
            "title": "TINGGI: Influencer Bertanda — @politikmalaysia2024 Aktiviti Luar Biasa",
            "description": "Akaun bertanda @politikmalaysia2024 (3.1M followers) menerbitkan 47 post "
                           "dalam 4 jam — 8× kadar biasa. 94% kandungan berkaitan nepotisme PM.",
            "severity": "high",
            "status": "active",
            "alert_type": "influencer_amplification",
            "source_type": "influencer",
            "trigger_data": {
                "username": "politikmalaysia2024",
                "followers": 3_100_000,
                "posts_in_4h": 47,
                "baseline_rate": 5.9,
                "influence_score": 94.2,
            },
            "affected_platforms": ["tiktok"],
            "affected_languages": ["ms"],
            "post_count": 47,
            "reach_estimate": 6_200_000,
            "created_at": ts(1.7),
        },
        {
            "id": uid(),
            "title": "TINGGI: Hashtag Surge — #HargaNaikLagi Naik 5.8× dalam 3 Jam",
            "description": "#HargaNaikLagi mencapai 6,788 mentions — 5.8× lebih tinggi dari baseline 3-hari. "
                           "Dipacu oleh satu video TikTok yang menjadi viral.",
            "severity": "high",
            "status": "active",
            "alert_type": "hashtag_surge",
            "trigger_data": {
                "hashtag": "harganaikLagi",
                "current_count": 6788,
                "baseline_avg": 1170,
                "multiplier": 5.8,
            },
            "affected_platforms": ["tiktok", "twitter"],
            "affected_languages": ["ms"],
            "post_count": 312,
            "reach_estimate": 7_800_000,
            "created_at": ts(2.4),
        },
        {
            "id": uid(),
            "title": "SEDERHANA: Kandungan Viral — Video 'Ringgit Jatuh' (2.1M Tayangan/3j)",
            "description": "Video TikTok @politikmalaysia2024 mengenai kejatuhan ringgit ke paras 1998 "
                           "mencapai 2.1M tayangan dalam 3 jam. Z-score: 4.2σ.",
            "severity": "medium",
            "status": "active",
            "alert_type": "viral_content",
            "source_type": "post",
            "trigger_data": {
                "platform": "tiktok",
                "views_3h": 2_100_000,
                "z_score": 4.2,
                "author": "politikmalaysia2024",
            },
            "affected_platforms": ["tiktok"],
            "affected_languages": ["ms"],
            "post_count": 44,
            "reach_estimate": 2_100_000,
            "created_at": ts(3.1),
        },
        {
            "id": uid(),
            "title": "TINGGI: Naratif Baru Muncul — EU Sawit Import Ban Fears",
            "description": "Kluster naratif baharu mengenai ancaman undang-undang alam sekitar EU "
                           "terhadap eksport minyak sawit Malaysia telah terbentuk. "
                           "390 post daripada 280 pengarang unik dalam 6 jam pertama.",
            "severity": "high",
            "status": "active",
            "alert_type": "narrative_spike",
            "source_id": nmap.get("sawit"),
            "source_type": "narrative",
            "trigger_data": {
                "post_count": 390,
                "unique_authors": 280,
                "hours_since_detection": 6,
                "narrative_key": "sawit",
            },
            "affected_platforms": ["twitter", "facebook", "news"],
            "affected_languages": ["en", "ms"],
            "post_count": 390,
            "reach_estimate": 3_200_000,
            "created_at": ts(5.8),
        },
        {
            "id": uid(),
            "title": "SEDERHANA: Teori Konspirasi MH370 Kembali Tular — Ulang Tahun Ke-10",
            "description": "Kandungan mendakwa kerajaan menyembunyikan data radar MH370 menjadi viral "
                           "sempena ulang tahun ke-10. Skor koordinasi: 0.55. Perlu pantauan.",
            "severity": "medium",
            "status": "acknowledged",
            "alert_type": "coordinated_behavior",
            "source_id": nmap.get("mh370"),
            "source_type": "narrative",
            "trigger_data": {
                "coordination_score": 0.55,
                "narrative_key": "mh370",
            },
            "affected_platforms": ["tiktok", "twitter"],
            "affected_languages": ["ms", "en"],
            "post_count": 411,
            "reach_estimate": 4_100_000,
            "created_at": ts(8.2),
            "acknowledged_by": "analyst_01",
            "acknowledged_at": ts(7.1),
            "notes": "MH370 10th anniversary. Expected spike. Monitoring for disinformation escalation.",
        },
    ]
    inserted = insert("alerts", alerts)
    print(f"  Inserted {len(inserted)} alerts")


# ═══════════════════════════════════════════════════════════════════════════════
#  9. ANALYTICS SNAPSHOTS (24 hourly)
# ═══════════════════════════════════════════════════════════════════════════════

def seed_analytics_snapshots():
    rows = []
    platform_names = ["twitter", "tiktok", "facebook", "news"]
    for h in range(23, -1, -1):
        bucket = NOW - timedelta(hours=h)
        bucket = bucket.replace(minute=0, second=0, microsecond=0)

        total = rng.randint(180, 420)
        neg_frac = rng.uniform(0.38, 0.62)
        pos_frac = rng.uniform(0.08, 0.22)
        neu_frac = max(0.05, 1 - neg_frac - pos_frac)

        rows.append({
            "bucket": bucket.isoformat(),
            "total_posts": total,
            "posts_by_platform": {
                "twitter": int(total * rng.uniform(0.22, 0.30)),
                "tiktok": int(total * rng.uniform(0.28, 0.38)),
                "facebook": int(total * rng.uniform(0.18, 0.28)),
                "news": int(total * rng.uniform(0.07, 0.14)),
            },
            "sentiment_distribution": {
                "negative": int(total * neg_frac),
                "neutral": int(total * neu_frac),
                "positive": int(total * pos_frac),
                "mixed": max(0, total - int(total * neg_frac) - int(total * neu_frac) - int(total * pos_frac)),
            },
            "active_alerts": rng.randint(4, 8),
        })
    inserted = insert("analytics_snapshots", rows, upsert_on="bucket")
    print(f"  Inserted {len(inserted)} analytics_snapshot rows")


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Seed Malaysia AI Monitor with sample data")
    parser.add_argument("--reset", action="store_true",
                        help="Delete existing seed data before inserting")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("  SENTINEL — Malaysia AI Monitor Seed Script")
    print(f"  Target: {SUPABASE_URL}")
    print(f"{'='*60}\n")

    if args.reset:
        print("── Resetting tables ──")
        reset_tables()
        print()

    print("── Seeding influencers ──")
    imap = seed_influencers()

    print("\n── Seeding narratives ──")
    nmap = seed_narratives()

    print("\n── Seeding hashtags ──")
    hmap = seed_hashtags()

    print("\n── Seeding entities ──")
    emap = seed_entities()

    print("\n── Seeding posts (+ junctions) ──")
    seed_posts(nmap, imap, hmap, emap)

    print("\n── Seeding narrative timeline ──")
    seed_narrative_timeline(nmap)

    print("\n── Seeding hashtag trends ──")
    seed_hashtag_trends(hmap)

    print("\n── Seeding alerts ──")
    seed_alerts(nmap)

    print("\n── Seeding analytics snapshots ──")
    seed_analytics_snapshots()

    print(f"\n{'='*60}")
    print("  Seed complete. Open http://localhost:3000 to see the dashboard.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
