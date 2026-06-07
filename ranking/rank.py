#!/usr/bin/env python3
"""Deterministic local ranker for the Redrob candidate discovery challenge.

The ranking step intentionally uses no external APIs, no hosted database, and
no GPU-only dependencies. It streams candidates from JSONL, keeps only the best
records in memory, and writes the exact CSV format required by the validator.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import heapq
import json
import math
import multiprocessing as mp
import os
import re
import sys
from pathlib import Path
from typing import Any


REFERENCE_DATE = dt.date(2026, 6, 7)

CORE_TERMS = {
    "retrieval": [
        "retrieval",
        "semantic search",
        "hybrid search",
        "dense retrieval",
        "sparse retrieval",
        "rag",
        "information retrieval",
        "search relevance",
        "matching system",
        "candidate matching",
        "document retrieval",
    ],
    "ranking": [
        "ranking",
        "ranker",
        "learning to rank",
        "ltr",
        "recommendation",
        "recommender",
        "personalization",
        "search ranking",
        "feed ranking",
        "marketplace ranking",
    ],
    "vector_search": [
        "embedding",
        "embeddings",
        "sentence-transformers",
        "sentence transformers",
        "bge",
        "e5",
        "vector database",
        "vector db",
        "vector search",
        "faiss",
        "milvus",
        "qdrant",
        "weaviate",
        "pinecone",
        "opensearch",
        "elasticsearch",
        "ann index",
        "hnsw",
    ],
    "evaluation": [
        "ndcg",
        "mrr",
        "mean reciprocal rank",
        "mean average precision",
        "ranking evaluation",
        "offline benchmark",
        "ab test",
        "a/b test",
        "experiment",
        "eval framework",
        "evaluation framework",
        "relevance judgment",
    ],
    "llm_ml": [
        "llm",
        "large language model",
        "fine-tuning",
        "finetuning",
        "lora",
        "qlora",
        "peft",
        "nlp",
        "transformer",
        "pytorch",
        "tensorflow",
        "scikit-learn",
        "xgboost",
    ],
    "python_systems": [
        "python",
        "fastapi",
        "airflow",
        "spark",
        "kafka",
        "mlops",
        "model serving",
        "inference",
        "production ml",
        "data pipeline",
    ],
}

CORE_WEIGHTS = {
    "retrieval": 0.22,
    "ranking": 0.20,
    "vector_search": 0.18,
    "evaluation": 0.16,
    "llm_ml": 0.13,
    "python_systems": 0.11,
}

PRODUCTION_TERMS = [
    "production",
    "deployed",
    "shipped",
    "launched",
    "owned",
    "scaled",
    "real users",
    "user-facing",
    "latency",
    "monitoring",
    "index refresh",
    "drift",
    "regression",
    "on-call",
    "a/b",
    "benchmark",
    "recruiter",
    "marketplace",
    "product",
    "pm",
]

STRONG_AI_TITLES = [
    "ai engineer",
    "machine learning engineer",
    "ml engineer",
    "applied scientist",
    "nlp engineer",
    "search engineer",
    "recommendation engineer",
    "ranking engineer",
    "mlops engineer",
    "data scientist",
]

ADJACENT_ENGINEERING_TITLES = [
    "software engineer",
    "backend engineer",
    "data engineer",
    "analytics engineer",
    "platform engineer",
    "research engineer",
]

NEGATIVE_TITLE_TERMS = [
    "marketing",
    "sales",
    "sales executive",
    "hr manager",
    "human resources",
    "graphic designer",
    "content writer",
    "copywriter",
    "accountant",
    "finance manager",
    "mechanical engineer",
    "civil engineer",
    "electrical engineer",
    "hardware engineer",
    "customer support",
    "operations manager",
    "recruiter",
    "business development",
]

SERVICES_COMPANIES = [
    "tcs",
    "tata consultancy",
    "infosys",
    "wipro",
    "accenture",
    "cognizant",
    "capgemini",
    "hcl",
    "tech mahindra",
    "ltimindtree",
    "mindtree",
    "mphasis",
    "ust",
    "persistent",
    "deloitte",
    "ey",
    "kpmg",
    "pwc",
]

GOOD_INDIAN_LOCATIONS = [
    "pune",
    "noida",
    "delhi",
    "gurgaon",
    "gurugram",
    "ncr",
    "mumbai",
    "hyderabad",
    "bengaluru",
    "bangalore",
]

CV_SPEECH_ROBOTICS_TERMS = [
    "computer vision",
    "image classification",
    "object detection",
    "speech recognition",
    "tts",
    "robotics",
    "gan",
    "gans",
]

PROFICIENCY_WEIGHT = {
    "beginner": 0.25,
    "intermediate": 0.55,
    "advanced": 0.80,
    "expert": 1.00,
}

ALL_CORE_TERMS = tuple(term for terms in CORE_TERMS.values() for term in terms)
CORE_WEIGHT_TOTAL = sum(CORE_WEIGHTS.values())


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def lower_join(parts: list[Any]) -> str:
    return " ".join(str(part or "") for part in parts).lower()


def parse_date(value: Any) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def count_term_hits(text: str, terms: list[str]) -> int:
    return sum(1 for term in terms if term in text)


def has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def candidate_number(candidate_id: str) -> int:
    match = re.search(r"(\d+)$", candidate_id or "")
    return int(match.group(1)) if match else 9999999


def flatten_candidate(candidate: dict[str, Any]) -> tuple[str, list[str]]:
    profile = candidate.get("profile", {}) or {}
    career = candidate.get("career_history", []) or []
    education = candidate.get("education", []) or []
    certifications = candidate.get("certifications", []) or []
    skills = candidate.get("skills", []) or []

    skill_names = [str(item.get("name", "")).strip() for item in skills if item.get("name")]
    parts: list[Any] = [
        profile.get("headline"),
        profile.get("summary"),
        profile.get("current_title"),
        profile.get("current_industry"),
        profile.get("location"),
        profile.get("country"),
    ]

    for role in career:
        parts.extend(
            [
                role.get("title"),
                role.get("industry"),
                role.get("company"),
                role.get("description"),
            ]
        )

    for item in education:
        parts.extend([item.get("degree"), item.get("field_of_study"), item.get("institution")])

    for item in certifications:
        parts.extend([item.get("name"), item.get("issuer")])

    parts.extend(skill_names)
    return lower_join(parts), [name.lower() for name in skill_names]


def category_score(text: str, skill_names: list[str], terms: list[str]) -> float:
    text_hits = count_term_hits(text, terms)
    skill_hits = 0
    for skill in skill_names:
        if any(term in skill or skill in term for term in terms if len(term) >= 3):
            skill_hits += 1
    return clamp((0.20 * text_hits) + (0.22 * skill_hits))


def score_technical_fit(text: str, skill_names: list[str]) -> tuple[float, dict[str, float]]:
    components: dict[str, float] = {}
    weighted = 0.0
    for category, terms in CORE_TERMS.items():
        score = category_score(text, skill_names, terms)
        components[category] = score
        weighted += score * CORE_WEIGHTS[category]
    total = weighted / CORE_WEIGHT_TOTAL
    return clamp(total), components


def score_role_title(title: str, text: str) -> float:
    title_l = title.lower()
    if has_any(title_l, STRONG_AI_TITLES):
        return 1.0
    if has_any(title_l, ADJACENT_ENGINEERING_TITLES):
        return 0.58 if has_any(text, ["retrieval", "ranking", "embedding", "ml", "nlp"]) else 0.44
    if has_any(title_l, NEGATIVE_TITLE_TERMS):
        return 0.05
    if "engineer" in title_l or "scientist" in title_l:
        return 0.48
    if "manager" in title_l or "analyst" in title_l:
        return 0.25
    return 0.18


def score_experience(years: float) -> float:
    if 5.0 <= years <= 9.0:
        return clamp(1.0 - (abs(years - 7.0) / 8.0), 0.74, 1.0)
    if 4.0 <= years < 5.0:
        return 0.68
    if 9.0 < years <= 11.0:
        return 0.66
    if 3.0 <= years < 4.0:
        return 0.42
    if 11.0 < years <= 13.0:
        return 0.42
    return 0.12


def score_location(candidate: dict[str, Any]) -> float:
    profile = candidate.get("profile", {}) or {}
    signals = candidate.get("redrob_signals", {}) or {}
    country = str(profile.get("country", "")).lower()
    location = str(profile.get("location", "")).lower()
    work_mode = str(signals.get("preferred_work_mode", "")).lower()

    score = 0.0
    if "india" in country:
        score += 0.46
    elif any(city in location for city in GOOD_INDIAN_LOCATIONS):
        score += 0.36
    else:
        score += 0.08

    if any(city in location for city in GOOD_INDIAN_LOCATIONS):
        score += 0.30
    if signals.get("willing_to_relocate") is True:
        score += 0.16
    if work_mode in {"hybrid", "flexible", "onsite"}:
        score += 0.08
    return clamp(score)


def score_behavior(signals: dict[str, Any]) -> tuple[float, dict[str, float]]:
    last_active = parse_date(signals.get("last_active_date"))
    days_inactive = 365
    if last_active:
        days_inactive = max(0, (REFERENCE_DATE - last_active).days)

    if days_inactive <= 14:
        recency = 1.0
    elif days_inactive <= 30:
        recency = 0.86
    elif days_inactive <= 60:
        recency = 0.62
    elif days_inactive <= 120:
        recency = 0.34
    else:
        recency = 0.08

    response_rate = clamp(safe_float(signals.get("recruiter_response_rate")))
    response_hours = safe_float(signals.get("avg_response_time_hours"), 999.0)
    response_time = clamp(1.0 - (response_hours / 168.0))
    notice = safe_int(signals.get("notice_period_days"), 180)
    notice_score = 1.0 if notice <= 30 else 0.72 if notice <= 60 else 0.34 if notice <= 90 else 0.10
    github_raw = safe_float(signals.get("github_activity_score"), -1.0)
    github = 0.0 if github_raw < 0 else clamp(github_raw / 100.0)
    profile_complete = clamp(safe_float(signals.get("profile_completeness_score")) / 100.0)
    interview = clamp(safe_float(signals.get("interview_completion_rate")))
    offer_raw = safe_float(signals.get("offer_acceptance_rate"), -1.0)
    offer = 0.45 if offer_raw < 0 else clamp(offer_raw)

    recruiter_attention = clamp(
        0.38 * math.log1p(safe_int(signals.get("saved_by_recruiters_30d"))) / math.log(21)
        + 0.32 * math.log1p(safe_int(signals.get("profile_views_received_30d"))) / math.log(301)
        + 0.30 * math.log1p(safe_int(signals.get("search_appearance_30d"))) / math.log(1001)
    )

    verified = (
        (0.38 if signals.get("verified_email") else 0.0)
        + (0.38 if signals.get("verified_phone") else 0.0)
        + (0.24 if signals.get("linkedin_connected") else 0.0)
    )

    pieces = {
        "recency": recency,
        "response_rate": response_rate,
        "response_time": response_time,
        "open_to_work": 1.0 if signals.get("open_to_work_flag") else 0.0,
        "notice": notice_score,
        "github": github,
        "profile_complete": profile_complete,
        "interview": interview,
        "offer": offer,
        "recruiter_attention": recruiter_attention,
        "verified": verified,
    }

    weighted = (
        0.17 * pieces["recency"]
        + 0.16 * pieces["response_rate"]
        + 0.08 * pieces["response_time"]
        + 0.12 * pieces["open_to_work"]
        + 0.11 * pieces["notice"]
        + 0.08 * pieces["github"]
        + 0.07 * pieces["profile_complete"]
        + 0.09 * pieces["interview"]
        + 0.04 * pieces["offer"]
        + 0.05 * pieces["recruiter_attention"]
        + 0.03 * pieces["verified"]
    )
    return clamp(weighted), pieces


def score_career_evidence(candidate: dict[str, Any], text: str, tech_components: dict[str, float]) -> float:
    profile = candidate.get("profile", {}) or {}
    career = candidate.get("career_history", []) or []

    career_text = lower_join(
        [
            *(role.get("title") for role in career),
            *(role.get("industry") for role in career),
            *(role.get("company") for role in career),
            *(role.get("description") for role in career),
        ]
    )
    career_tech, career_components = score_technical_fit(career_text, [])

    production = clamp(count_term_hits(career_text, PRODUCTION_TERMS) / 8.0)
    search_stack = clamp(
        (
            career_components["retrieval"]
            + career_components["ranking"]
            + career_components["vector_search"]
            + career_components["evaluation"]
        )
        / 3.2
    )

    current_industry = str(profile.get("current_industry", "")).lower()
    product_industry = 1.0 if has_any(current_industry, ["software", "internet", "saas", "product", "fintech", "e-commerce", "hr tech"]) else 0.0

    long_relevant_role = 0.0
    for role in career:
        duration = safe_int(role.get("duration_months"))
        role_text = lower_join([role.get("title"), role.get("description"), role.get("industry")])
        if duration >= 18 and has_any(role_text, ["retrieval", "ranking", "recommendation", "search", "ml", "ai", "nlp"]):
            long_relevant_role = max(long_relevant_role, clamp(duration / 48.0))

    return clamp(
        0.30 * production
        + 0.34 * search_stack
        + 0.14 * product_industry
        + 0.16 * long_relevant_role
        + 0.06 * career_tech
    )


def services_only_penalty(candidate: dict[str, Any], text: str) -> float:
    profile = candidate.get("profile", {}) or {}
    career = candidate.get("career_history", []) or []
    company_blob = lower_join(
        [profile.get("current_company"), *(role.get("company") for role in career), *(role.get("industry") for role in career)]
    )
    if not company_blob:
        return 0.0
    service_hits = sum(1 for term in SERVICES_COMPANIES if term in company_blob)
    it_services_roles = sum(1 for role in career if "it services" in str(role.get("industry", "")).lower())
    all_services_like = career and it_services_roles >= max(1, len(career) - 1)
    has_product_evidence = has_any(text, ["product", "saas", "marketplace", "consumer", "users", "launched", "growth"])

    if (service_hits >= 2 or all_services_like) and not has_product_evidence:
        return 0.12
    if service_hits >= 1 and not has_product_evidence:
        return 0.05
    return 0.0


def honeypot_penalty(candidate: dict[str, Any], text: str) -> float:
    profile = candidate.get("profile", {}) or {}
    skills = candidate.get("skills", []) or []
    years = safe_float(profile.get("years_of_experience"))

    suspicious = 0.0
    zero_expert = 0
    overclaimed = 0
    advanced_core = 0

    for skill in skills:
        name = str(skill.get("name", "")).lower()
        proficiency = str(skill.get("proficiency", "")).lower()
        duration = safe_int(skill.get("duration_months"))
        endorsements = safe_int(skill.get("endorsements"))

        if proficiency == "expert" and duration <= 3 and endorsements <= 2:
            zero_expert += 1
        if duration > int(years * 12) + 24 and years > 0:
            overclaimed += 1
        if proficiency in {"advanced", "expert"} and has_any(name, ALL_CORE_TERMS):
            advanced_core += 1

    if zero_expert >= 3:
        suspicious += 0.14
    if overclaimed >= 3:
        suspicious += 0.09
    if years < 2.0 and advanced_core >= 6:
        suspicious += 0.15
    if "expert" in text and "0 months" in text:
        suspicious += 0.05
    return clamp(suspicious, 0.0, 0.26)


def keyword_stuffing_penalty(role_score: float, tech_score: float, career_score: float, text: str) -> float:
    core_hits = sum(count_term_hits(text, terms) for terms in CORE_TERMS.values())
    if core_hits >= 18 and career_score < 0.35 and role_score < 0.35:
        return 0.18
    if core_hits >= 12 and career_score < 0.25:
        return 0.10
    if "langchain" in text and tech_score < 0.42 and career_score < 0.36:
        return 0.06
    return 0.0


def ai_course_trap_penalty(role_score: float, career_score: float, text: str) -> float:
    side_project_terms = [
        "ai enthusiast",
        "exploring ai",
        "exploring ai & genai",
        "online courses on rag",
        "experimenting with langchain",
        "openai api for side projects",
        "augment my work",
        "grow my ai capabilities",
        "typical responsibilities of the role",
    ]
    if role_score < 0.42 and career_score < 0.42 and has_any(text, side_project_terms):
        return 0.24
    if career_score < 0.28 and has_any(text, ["langchain", "openai api", "prompt engineering"]):
        return 0.08
    return 0.0


def domain_mismatch_penalty(text: str, tech_components: dict[str, float]) -> float:
    cv_speech = count_term_hits(text, CV_SPEECH_ROBOTICS_TERMS)
    retrieval_side = tech_components["retrieval"] + tech_components["ranking"] + tech_components["evaluation"]
    if cv_speech >= 4 and retrieval_side < 0.55:
        return 0.10
    if cv_speech >= 2 and retrieval_side < 0.25:
        return 0.05
    return 0.0


def experience_band_penalty(years: float) -> float:
    if years < 3.0:
        return 0.16
    if years < 4.0:
        return 0.07
    if years > 15.0:
        return 0.16
    if years > 13.0:
        return 0.11
    if years > 11.0:
        return 0.05
    return 0.0


def logistics_penalty(candidate: dict[str, Any]) -> float:
    profile = candidate.get("profile", {}) or {}
    signals = candidate.get("redrob_signals", {}) or {}
    country = str(profile.get("country", "")).lower()
    location = str(profile.get("location", "")).lower()
    in_india = "india" in country or any(city in location for city in GOOD_INDIAN_LOCATIONS)
    if in_india:
        return 0.0
    return 0.07 if signals.get("willing_to_relocate") else 0.12


def score_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    profile = candidate.get("profile", {}) or {}
    signals = candidate.get("redrob_signals", {}) or {}
    text, skill_names = flatten_candidate(candidate)
    current_title = str(profile.get("current_title", "Unknown"))
    years = safe_float(profile.get("years_of_experience"))

    tech_score, tech_components = score_technical_fit(text, skill_names)
    role_score = score_role_title(current_title, text)
    experience_score = score_experience(years)
    location_score = score_location(candidate)
    behavior_score, behavior_components = score_behavior(signals)
    career_score = score_career_evidence(candidate, text, tech_components)

    penalties = {
        "negative_title": 0.0,
        "services_only": services_only_penalty(candidate, text),
        "honeypot_suspicion": honeypot_penalty(candidate, text),
        "keyword_stuffing": keyword_stuffing_penalty(role_score, tech_score, career_score, text),
        "ai_course_trap": ai_course_trap_penalty(role_score, career_score, text),
        "domain_mismatch": domain_mismatch_penalty(text, tech_components),
        "experience_band": experience_band_penalty(years),
        "logistics": logistics_penalty(candidate),
        "stale_or_unresponsive": 0.0,
        "notice_period": 0.0,
    }

    title_l = current_title.lower()
    if has_any(title_l, NEGATIVE_TITLE_TERMS) and not (tech_score > 0.72 and career_score > 0.52):
        penalties["negative_title"] = 0.20 if tech_score > 0.52 else 0.34

    last_active = parse_date(signals.get("last_active_date"))
    inactive_days = (REFERENCE_DATE - last_active).days if last_active else 365
    if inactive_days > 120 and safe_float(signals.get("recruiter_response_rate")) < 0.20:
        penalties["stale_or_unresponsive"] = 0.14
    elif inactive_days > 60 and safe_float(signals.get("recruiter_response_rate")) < 0.12:
        penalties["stale_or_unresponsive"] = 0.08

    notice_days = safe_int(signals.get("notice_period_days"))
    if notice_days > 120:
        penalties["notice_period"] = 0.06
    elif notice_days > 90:
        penalties["notice_period"] = 0.035

    penalty_total = sum(penalties.values())
    raw_score = (
        0.28 * tech_score
        + 0.24 * career_score
        + 0.15 * role_score
        + 0.10 * experience_score
        + 0.10 * location_score
        + 0.16 * behavior_score
        - penalty_total
    )

    raw_score = clamp(raw_score, -0.5, 1.0)
    top_skills = select_top_skills(candidate)
    reasoning = build_reasoning(
        candidate,
        tech_components,
        {
            "technical": tech_score,
            "career": career_score,
            "role": role_score,
            "experience": experience_score,
            "location": location_score,
            "behavior": behavior_score,
            "penalty": penalty_total,
        },
        penalties,
        top_skills,
    )

    return {
        "candidate_id": candidate.get("candidate_id", ""),
        "raw_score": raw_score,
        "reasoning": reasoning,
        "profile": {
            "name": profile.get("anonymized_name", ""),
            "headline": profile.get("headline", ""),
            "current_title": current_title,
            "current_company": profile.get("current_company", ""),
            "location": profile.get("location", ""),
            "country": profile.get("country", ""),
            "years_of_experience": years,
            "industry": profile.get("current_industry", ""),
        },
        "top_skills": top_skills,
        "signals": summarize_signals(signals),
        "components": {
            "technical": round(tech_score, 4),
            "career": round(career_score, 4),
            "role": round(role_score, 4),
            "experience": round(experience_score, 4),
            "location": round(location_score, 4),
            "behavior": round(behavior_score, 4),
            "penalty": round(penalty_total, 4),
        },
        "technical_components": {key: round(value, 4) for key, value in tech_components.items()},
        "behavior_components": {key: round(value, 4) for key, value in behavior_components.items()},
        "penalties": {key: round(value, 4) for key, value in penalties.items() if value > 0},
    }


def select_top_skills(candidate: dict[str, Any], limit: int = 7) -> list[dict[str, Any]]:
    skills = candidate.get("skills", []) or []

    def weight(skill: dict[str, Any]) -> float:
        proficiency = PROFICIENCY_WEIGHT.get(str(skill.get("proficiency", "")).lower(), 0.35)
        endorsements = math.log1p(safe_int(skill.get("endorsements"))) / math.log(101)
        duration = clamp(safe_int(skill.get("duration_months")) / 60.0)
        name = str(skill.get("name", "")).lower()
        core = 0.25 if has_any(name, ALL_CORE_TERMS) else 0.0
        return 0.45 * proficiency + 0.22 * endorsements + 0.18 * duration + core

    ranked = sorted(skills, key=weight, reverse=True)[:limit]
    return [
        {
            "name": item.get("name", ""),
            "proficiency": item.get("proficiency", ""),
            "endorsements": safe_int(item.get("endorsements")),
            "duration_months": safe_int(item.get("duration_months")),
        }
        for item in ranked
    ]


def summarize_signals(signals: dict[str, Any]) -> dict[str, Any]:
    last_active = parse_date(signals.get("last_active_date"))
    days_inactive = (REFERENCE_DATE - last_active).days if last_active else None
    salary = signals.get("expected_salary_range_inr_lpa", {}) or {}
    return {
        "open_to_work": bool(signals.get("open_to_work_flag")),
        "last_active_date": signals.get("last_active_date"),
        "days_inactive": days_inactive,
        "recruiter_response_rate": safe_float(signals.get("recruiter_response_rate")),
        "avg_response_time_hours": safe_float(signals.get("avg_response_time_hours")),
        "notice_period_days": safe_int(signals.get("notice_period_days")),
        "preferred_work_mode": signals.get("preferred_work_mode", ""),
        "willing_to_relocate": bool(signals.get("willing_to_relocate")),
        "github_activity_score": safe_float(signals.get("github_activity_score"), -1.0),
        "interview_completion_rate": safe_float(signals.get("interview_completion_rate")),
        "offer_acceptance_rate": safe_float(signals.get("offer_acceptance_rate"), -1.0),
        "saved_by_recruiters_30d": safe_int(signals.get("saved_by_recruiters_30d")),
        "profile_views_received_30d": safe_int(signals.get("profile_views_received_30d")),
        "salary_min_lpa": safe_float(salary.get("min")),
        "salary_max_lpa": safe_float(salary.get("max")),
    }


def build_reasoning(
    candidate: dict[str, Any],
    tech_components: dict[str, float],
    components: dict[str, float],
    penalties: dict[str, float],
    top_skills: list[dict[str, Any]],
) -> str:
    profile = candidate.get("profile", {}) or {}
    signals = candidate.get("redrob_signals", {}) or {}
    title = str(profile.get("current_title", "Candidate"))
    years = safe_float(profile.get("years_of_experience"))
    location = str(profile.get("location", ""))
    country = str(profile.get("country", ""))
    skills = [item.get("name", "") for item in top_skills[:5]]

    strongest = sorted(tech_components.items(), key=lambda item: item[1], reverse=True)
    strong_labels = [label.replace("_", " ") for label, value in strongest if value >= 0.45][:2]

    first = f"{title} with {years:.1f} years"
    if location or country:
        first += f" in {location or country}"
    if strong_labels:
        first += f"; strongest match is {', '.join(strong_labels)}"
    elif skills:
        first += f"; relevant skills include {', '.join(str(skill) for skill in skills[:3])}"
    first += "."

    signal_bits: list[str] = []
    if signals.get("open_to_work_flag"):
        signal_bits.append("open to work")
    response = safe_float(signals.get("recruiter_response_rate"))
    if response > 0:
        signal_bits.append(f"{response:.0%} recruiter response")
    notice = safe_int(signals.get("notice_period_days"))
    signal_bits.append(f"{notice}-day notice")
    github = safe_float(signals.get("github_activity_score"), -1.0)
    if github >= 0:
        signal_bits.append(f"GitHub score {github:.0f}")

    concern_bits: list[str] = []
    if penalties.get("negative_title", 0) > 0:
        concern_bits.append("current title is not a clean AI-engineering match")
    if penalties.get("services_only", 0) > 0:
        concern_bits.append("services-heavy background")
    if penalties.get("stale_or_unresponsive", 0) > 0:
        concern_bits.append("weak recent availability signals")
    if penalties.get("domain_mismatch", 0) > 0:
        concern_bits.append("some AI evidence skews away from retrieval/ranking")
    if penalties.get("experience_band", 0) > 0:
        concern_bits.append("experience is outside the JD sweet spot")
    if penalties.get("logistics", 0) > 0:
        concern_bits.append("location is a logistics stretch")
    if components["career"] < 0.34:
        concern_bits.append("limited production ranking evidence")

    second = "Signals: " + ", ".join(signal_bits[:4]) + "."
    if concern_bits:
        second += " Concern: " + "; ".join(concern_bits[:2]) + "."

    return clean_reasoning(first + " " + second)


def clean_reasoning(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip())
    return value[:420]


def load_candidates(path: Path, limit: int | None = None) -> Any:
    seen = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            seen += 1
            yield json.loads(line)
            if limit is not None and seen >= limit:
                break


def iter_line_batches(path: Path, batch_size: int, limit: int | None = None) -> Any:
    seen = 0
    batch: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            batch.append(line)
            seen += 1
            if len(batch) >= batch_size:
                yield batch
                batch = []
            if limit is not None and seen >= limit:
                break
    if batch:
        yield batch


def push_record(heap: list[tuple[tuple[float, int], dict[str, Any]]], record: dict[str, Any], top_k: int) -> None:
    key = (record["raw_score"], -candidate_number(record["candidate_id"]))
    if len(heap) < top_k:
        heapq.heappush(heap, (key, record))
    elif key > heap[0][0]:
        heapq.heapreplace(heap, (key, record))


def score_candidate_lines(args: tuple[list[str], int]) -> tuple[int, list[dict[str, Any]]]:
    lines, top_k = args
    heap: list[tuple[tuple[float, int], dict[str, Any]]] = []
    scanned = 0
    for line in lines:
        scanned += 1
        record = score_candidate(json.loads(line))
        push_record(heap, record, top_k)
    records = [record for _, record in heap]
    records.sort(key=lambda item: (-item["raw_score"], item["candidate_id"]))
    return scanned, records


def auto_worker_count() -> int:
    cpu_count = os.cpu_count() or 1
    return max(1, min(cpu_count, 12))


def rank_candidates(
    candidates_path: Path,
    top_k: int,
    limit: int | None = None,
    workers: int = 1,
    batch_size: int = 1000,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    heap: list[tuple[tuple[float, int], dict[str, Any]]] = []
    scanned = 0

    if workers <= 1:
        for candidate in load_candidates(candidates_path, limit=limit):
            scanned += 1
            push_record(heap, score_candidate(candidate), top_k)

            if scanned % 10000 == 0:
                print(f"scanned {scanned} candidates", file=sys.stderr)
    else:
        worker_count = max(1, workers)
        tasks = ((batch, top_k) for batch in iter_line_batches(candidates_path, batch_size=batch_size, limit=limit))
        with mp.Pool(processes=worker_count) as pool:
            for batch_scanned, batch_records in pool.imap_unordered(score_candidate_lines, tasks, chunksize=1):
                scanned += batch_scanned
                for record in batch_records:
                    push_record(heap, record, top_k)
                if scanned % 10000 < batch_scanned:
                    print(f"scanned {scanned} candidates", file=sys.stderr)

    records = [record for _, record in heap]
    records.sort(key=lambda item: (-item["raw_score"], item["candidate_id"]))
    apply_submission_scores(records)
    summary = {
        "scanned_candidates": scanned,
        "top_k": top_k,
        "reference_date": REFERENCE_DATE.isoformat(),
        "max_raw_score": max((item["raw_score"] for item in records), default=0.0),
        "min_raw_score": min((item["raw_score"] for item in records), default=0.0),
    }
    return records, summary


def apply_submission_scores(records: list[dict[str, Any]]) -> None:
    if not records:
        return
    raw_values = [item["raw_score"] for item in records]
    max_raw = max(raw_values)
    min_raw = min(raw_values)
    spread = max(max_raw - min_raw, 1e-9)
    previous = 1.0

    for index, record in enumerate(records, start=1):
        if spread < 1e-6:
            normalized = 0.995 - ((index - 1) * 0.003)
        else:
            normalized = 0.605 + (0.39 * ((record["raw_score"] - min_raw) / spread))
        normalized = min(normalized, previous - 0.0001)
        normalized = clamp(normalized, 0.001, 0.999)
        record["rank"] = index
        record["score"] = round(normalized, 4)
        previous = normalized


def write_submission(records: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["candidate_id", "rank", "score", "reasoning"])
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "candidate_id": record["candidate_id"],
                    "rank": record["rank"],
                    "score": f"{record['score']:.4f}",
                    "reasoning": record["reasoning"],
                }
            )


def write_json(records: list[dict[str, Any]], summary: dict[str, Any], json_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": summary,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "records": records,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rank Redrob candidates for the Senior AI Engineer JD.")
    parser.add_argument("--candidates", required=True, type=Path, help="Path to candidates.jsonl")
    parser.add_argument("--out", required=True, type=Path, help="Submission CSV output path")
    parser.add_argument("--json-out", type=Path, help="Optional UI/debug JSON output path")
    parser.add_argument("--top-k", type=int, default=100, help="Number of candidates to rank")
    parser.add_argument("--limit", type=int, help="Optional candidate scan limit for demos/tests")
    parser.add_argument(
        "--workers",
        type=int,
        default=0,
        help="Parallel worker processes. 0 chooses a safe CPU-based default; 1 runs single-process.",
    )
    parser.add_argument("--batch-size", type=int, default=1000, help="JSONL lines per multiprocessing task")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    if not args.candidates.exists():
        print(f"Candidate file not found: {args.candidates}", file=sys.stderr)
        return 2
    if args.top_k <= 0:
        print("--top-k must be positive", file=sys.stderr)
        return 2
    if args.batch_size <= 0:
        print("--batch-size must be positive", file=sys.stderr)
        return 2

    workers = auto_worker_count() if args.workers == 0 else args.workers
    if workers < 1:
        print("--workers must be 0 or a positive integer", file=sys.stderr)
        return 2

    records, summary = rank_candidates(
        args.candidates,
        top_k=args.top_k,
        limit=args.limit,
        workers=workers,
        batch_size=args.batch_size,
    )
    if len(records) < args.top_k:
        print(f"Only ranked {len(records)} candidates from the provided file.", file=sys.stderr)

    write_submission(records, args.out)
    if args.json_out:
        write_json(records, summary, args.json_out)

    print(json.dumps({"out": str(args.out), "json_out": str(args.json_out or ""), "workers": workers, **summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
