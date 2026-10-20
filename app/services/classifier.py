"""Deterministic, explainable baseline classification and priority engine.

Uses transparent keyword/phrase pattern matching, clear precedence rules, and
explicit ambiguity detection.
"""

import re
from typing import Dict, List, Tuple
from app.models.schemas import Category, Priority, SupportTeam

# ---------------------------------------------------------------------------
# Lexicon configuration for category matching
# Weighted phrases (higher weight for multi-word or strong indicator phrases)
# ---------------------------------------------------------------------------

CATEGORY_LEXICONS: Dict[Category, Dict[str, float]] = {
    Category.BILLING: {
        "charged twice": 3.0,
        "double charge": 3.0,
        "double billing": 3.0,
        "unauthorized charge": 3.0,
        "incorrect charge": 2.5,
        "refund": 2.5,
        "chargeback": 2.5,
        "invoice": 2.0,
        "billing": 2.0,
        "subscription": 2.0,
        "credit card": 2.0,
        "payment": 1.5,
        "overcharged": 2.0,
        "charged": 1.5,
        "receipt": 1.5,
        "pricing": 1.5,
        "fee": 1.2,
        "bank": 1.2,
        "transaction": 1.5,
        "renew": 1.2,
        "debit": 1.5,
    },
    Category.TECHNICAL: {
        "complete outage": 3.5,
        "service outage": 3.5,
        "server down": 3.0,
        "system down": 3.0,
        "production down": 3.0,
        "500 internal server error": 3.0,
        "crash": 2.5,
        "crashed": 2.5,
        "outage": 2.5,
        "stack trace": 2.5,
        "nullpointer": 2.5,
        "api error": 2.0,
        "timeout": 2.0,
        "bug": 1.8,
        "broken": 1.8,
        "glitch": 1.5,
        "slow": 1.2,
        "latency": 1.5,
        "error code": 1.8,
        "failed to load": 1.8,
        "500": 1.5,
        "502": 1.5,
        "503": 1.5,
        "504": 1.5,
        "endpoint": 1.2,
        "exception": 1.8,
    },
    Category.ACCESS: {
        "unauthorized access": 3.5,
        "account hacked": 3.5,
        "suspicious login": 3.0,
        "account compromised": 3.5,
        "locked out": 3.0,
        "reset password": 2.5,
        "password reset": 2.5,
        "forgot password": 2.0,
        "2fa": 2.5,
        "mfa": 2.5,
        "two-factor": 2.5,
        "sso": 2.0,
        "single sign-on": 2.5,
        "permission denied": 2.5,
        "access denied": 2.5,
        "login": 1.5,
        "log in": 1.5,
        "signin": 1.5,
        "sign in": 1.5,
        "credentials": 1.8,
        "authenticator": 2.0,
        "session expired": 1.5,
        "unauthorized": 2.0,
    },
    Category.GENERAL: {
        "how do i": 2.5,
        "how to": 2.5,
        "documentation": 2.0,
        "user guide": 2.0,
        "feature request": 2.5,
        "roadmap": 2.0,
        "office hours": 2.0,
        "support hours": 2.0,
        "general question": 2.0,
        "information": 1.5,
        "inquiry": 1.5,
        "inquire": 1.5,
        "feedback": 1.5,
        "suggestion": 1.5,
        "contact sales": 2.0,
        "pricing plans": 1.5,
        "help": 1.0,
        "question": 1.2,
    },
}

# ---------------------------------------------------------------------------
# Priority triggers with explicit precedence
# ---------------------------------------------------------------------------

HIGH_PRIORITY_TRIGGERS: List[Tuple[str, str]] = [
    # Security / unauthorized access triggers
    (r"\b(unauthorized\s+access|account\s+hacked|compromised|hacked|stolen\s+credentials|suspicious\s+login|security\s+breach)\b",
     "Suspected unauthorized account access / security alert"),
    # Complete service outage triggers
    (r"\b(service\s+outage|complete\s+outage|production\s+down|system\s+down|server\s+down|entire\s+team\s+blocked|all\s+users\s+affected)\b",
     "Complete service outage affecting users"),
    # Severe financial impact triggers
    (r"\b(charged\s+twice|double\s+charge|double\s+billing|fraudulent\s+charge|unauthorized\s+charge|charged\s+multiple\s+times)\b",
     "Duplicate or unauthorized billing transaction with immediate financial impact"),
    (r"\b(payment\s+failed.*?(charged|deducted)|deducted\s+without\s+order)\b",
     "Payment failure resulting in deducted funds"),
]

MEDIUM_PRIORITY_TRIGGERS: List[Tuple[str, str]] = [
    # Blocked core workflow or significant malfunction
    (r"\b(locked\s+out|cannot\s+login|unable\s+to\s+login|password\s+reset\s+not\s+working|cannot\s+access\s+account)\b",
     "User locked out or unable to access account"),
    (r"\b(checkout\s+failing|cannot\s+export|blocked|blocking\s+our\s+work|core\s+feature|500\s+internal|crash\s+on\s+startup|api\s+timeout|data\s+loss)\b",
     "Significant feature malfunction or blocked workflow"),
    (r"\b(permission\s+denied|license\s+expired|cannot\s+submit|crash)\b",
     "Access restriction or application crash interrupting operations"),
]

# ---------------------------------------------------------------------------
# Team mapping
# ---------------------------------------------------------------------------

TEAM_MAPPING: Dict[Category, SupportTeam] = {
    Category.BILLING: SupportTeam.BILLING_SUPPORT,
    Category.TECHNICAL: SupportTeam.TECHNICAL_SUPPORT,
    Category.ACCESS: SupportTeam.ACCOUNT_SUPPORT,
    Category.GENERAL: SupportTeam.GENERAL_SUPPORT,
}


class ClassifierResult:
    """Encapsulates the output of the classification engine."""

    def __init__(
        self,
        category: Category,
        priority: Priority,
        assigned_team: SupportTeam,
        confidence_score: float,
        classification_explanation: str,
        needs_human_review: bool,
    ):
        self.category = category
        self.priority = priority
        self.assigned_team = assigned_team
        self.confidence_score = confidence_score
        self.classification_explanation = classification_explanation
        self.needs_human_review = needs_human_review


def score_category_signals(clean_text: str) -> Dict[Category, Tuple[float, List[str]]]:
    """Calculate weighted phrase match scores for each category."""
    scores: Dict[Category, Tuple[float, List[str]]] = {}

    for cat, lexicon in CATEGORY_LEXICONS.items():
        total_score = 0.0
        matched_phrases: List[str] = []

        for phrase, weight in lexicon.items():
            # Use regex word boundaries for accurate phrase isolation
            pattern = r"\b" + re.escape(phrase) + r"\b"
            matches = len(re.findall(pattern, clean_text, re.IGNORECASE))
            if matches > 0:
                total_score += weight * matches
                matched_phrases.append(f"'{phrase}' (x{matches})")

        scores[cat] = (total_score, matched_phrases)

    return scores


def determine_priority(clean_text: str, category: Category) -> Tuple[Priority, str]:
    """Determine priority using strict hierarchical precedence rules.

    High > Medium > Low.
    """
    # 1. Check High Priority signals first
    for pattern, rationale in HIGH_PRIORITY_TRIGGERS:
        if re.search(pattern, clean_text, re.IGNORECASE):
            return Priority.HIGH, f"Assigned High priority: {rationale}."

    # 2. Check Medium Priority signals
    for pattern, rationale in MEDIUM_PRIORITY_TRIGGERS:
        if re.search(pattern, clean_text, re.IGNORECASE):
            return Priority.MEDIUM, f"Assigned Medium priority: {rationale}."

    # 3. Default priority mapping by category context
    if category in (Category.TECHNICAL, Category.ACCESS):
        return Priority.MEDIUM, "Assigned Medium priority default for operational/technical disruption."

    return Priority.LOW, "Assigned Low priority: General enquiry or non-urgent inquiry with no critical triggers."


def classify_ticket(message: str) -> ClassifierResult:
    """Classify a support ticket message deterministically.

    Returns:
        ClassifierResult with category, priority, team, explainable confidence,
        and human review flag.
    """
    clean_text = " " + message.lower().strip() + " "

    # Calculate category match scores
    scores = score_category_signals(clean_text)

    # Sort categories by score descending
    sorted_scores = sorted(
        scores.items(),
        key=lambda item: item[1][0],
        reverse=True
    )

    top_cat, (top_score, top_matches) = sorted_scores[0]
    second_cat, (second_score, second_matches) = sorted_scores[1]

    needs_human_review = False
    confidence_score: float
    explanation_parts: List[str] = []

    # Case 1: No keywords matched across any category
    if top_score <= 0.0:
        assigned_category = Category.GENERAL
        needs_human_review = True
        confidence_score = 0.35
        explanation = (
            "No domain-specific keywords identified. Categorized as General with "
            "mandatory human review required."
        )
    # Case 2: Ambiguous ticket (two categories have equal or nearly equal scores)
    elif second_score > 0 and (top_score - second_score) < 0.6:
        assigned_category = top_cat
        needs_human_review = True
        # Calibrated heuristic score representing ambiguity
        confidence_score = 0.48
        explanation = (
            f"Ambiguous classification between {top_cat.value} ({', '.join(top_matches)}) "
            f"and {second_cat.value} ({', '.join(second_matches)}). "
            f"Flagged for human triage."
        )
    # Case 3: Confident single-category match
    else:
        assigned_category = top_cat
        # Heuristic confidence calculation bounded between 0.65 and 0.95
        confidence_score = min(0.95, 0.60 + min(0.35, (top_score / 10.0)))
        confidence_score = round(confidence_score, 2)
        explanation = (
            f"Classified as {top_cat.value} based on matched signals: {', '.join(top_matches)}."
        )

    # Determine priority based on documented rules
    priority, priority_rationale = determine_priority(clean_text, assigned_category)

    # Full explainable rationale
    full_explanation = f"{explanation} {priority_rationale}"
    assigned_team = TEAM_MAPPING[assigned_category]

    return ClassifierResult(
        category=assigned_category,
        priority=priority,
        assigned_team=assigned_team,
        confidence_score=confidence_score,
        classification_explanation=full_explanation,
        needs_human_review=needs_human_review,
    )
