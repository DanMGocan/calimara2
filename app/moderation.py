import os
import logging
import httpx
from typing import Dict, Tuple, Optional
from enum import Enum

logger = logging.getLogger(__name__)

# Configuration from environment
PERSPECTIVE_API_KEY = os.getenv("PERSPECTIVE_API_KEY", "")
MODERATION_ENABLED = os.getenv("MODERATION_ENABLED", "True").lower() == "true"
TOXICITY_THRESHOLD_AUTO_APPROVE = float(os.getenv("TOXICITY_THRESHOLD_AUTO_APPROVE", "0.3"))
TOXICITY_THRESHOLD_AUTO_REJECT = float(os.getenv("TOXICITY_THRESHOLD_AUTO_REJECT", "0.8"))

PERSPECTIVE_API_URL = "https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze"

class ModerationStatus(str, Enum):
    APPROVED = "approved"
    PENDING = "pending"
    REJECTED = "rejected"
    FLAGGED = "flagged"

class ModerationResult:
    def __init__(self, status: ModerationStatus, toxicity_score: float, reason: str):
        self.status = status
        self.toxicity_score = toxicity_score
        self.reason = reason

async def analyze_content_toxicity(text: str, language: str = "ro") -> Dict[str, float]:
    """
    Analyze text using Google Perspective API
    Returns toxicity scores for different attributes
    """
    if not PERSPECTIVE_API_KEY or not MODERATION_ENABLED:
        logger.warning("Perspective API not configured or disabled")
        return {"TOXICITY": 0.0}
    
    try:
        data = {
            'comment': {'text': text},
            'requestedAttributes': {
                'TOXICITY': {},
                'SEVERE_TOXICITY': {},
                'IDENTITY_ATTACK': {},
                'INSULT': {},
                'PROFANITY': {},
                'THREAT': {}
            },
            'languages': [language],
            'doNotStore': True  # Don't store data for privacy
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{PERSPECTIVE_API_URL}?key={PERSPECTIVE_API_KEY}",
                json=data
            )
            
            if response.status_code == 200:
                result = response.json()
                scores = {}
                
                for attribute, data in result.get('attributeScores', {}).items():
                    score = data.get('summaryScore', {}).get('value', 0.0)
                    scores[attribute] = score
                
                logger.info(f"Perspective API analysis completed. TOXICITY: {scores.get('TOXICITY', 0.0):.3f}")
                return scores
            else:
                logger.error(f"Perspective API error: {response.status_code} - {response.text}")
                return {"TOXICITY": 0.0}  # Fail safe - approve if API fails
                
    except Exception as e:
        logger.error(f"Error calling Perspective API: {e}")
        return {"TOXICITY": 0.0}  # Fail safe - approve if API fails

def determine_moderation_status(toxicity_scores: Dict[str, float], content_type: str = "comment") -> ModerationResult:
    """
    Determine moderation status based on toxicity scores
    """
    toxicity = toxicity_scores.get("TOXICITY", 0.0)
    severe_toxicity = toxicity_scores.get("SEVERE_TOXICITY", 0.0)
    identity_attack = toxicity_scores.get("IDENTITY_ATTACK", 0.0)
    threat = toxicity_scores.get("THREAT", 0.0)
    
    # Auto-reject for severe cases
    if (toxicity >= TOXICITY_THRESHOLD_AUTO_REJECT or 
        severe_toxicity >= 0.7 or 
        identity_attack >= 0.7 or 
        threat >= 0.7):
        return ModerationResult(
            status=ModerationStatus.REJECTED,
            toxicity_score=toxicity,
            reason=f"High toxicity detected (toxicity: {toxicity:.2f})"
        )
    
    # Flag for manual review for medium toxicity
    if (toxicity >= TOXICITY_THRESHOLD_AUTO_APPROVE or 
        severe_toxicity >= 0.4 or 
        identity_attack >= 0.4 or 
        threat >= 0.4):
        return ModerationResult(
            status=ModerationStatus.FLAGGED,
            toxicity_score=toxicity,
            reason=f"Medium toxicity detected - manual review required (toxicity: {toxicity:.2f})"
        )
    
    # Auto-approve for low toxicity
    return ModerationResult(
        status=ModerationStatus.APPROVED,
        toxicity_score=toxicity,
        reason=f"Content approved - low toxicity (toxicity: {toxicity:.2f})"
    )

async def moderate_comment(content: str) -> ModerationResult:
    """
    Analyze and moderate a comment
    """
    if not MODERATION_ENABLED:
        return ModerationResult(
            status=ModerationStatus.APPROVED,
            toxicity_score=0.0,
            reason="Moderation disabled"
        )
    
    toxicity_scores = await analyze_content_toxicity(content)
    return determine_moderation_status(toxicity_scores, "comment")

async def moderate_post(title: str, content: str) -> ModerationResult:
    """
    Analyze and moderate a post (title + content)
    """
    if not MODERATION_ENABLED:
        return ModerationResult(
            status=ModerationStatus.APPROVED,
            toxicity_score=0.0,
            reason="Moderation disabled"
        )
    
    # Combine title and content for analysis
    full_text = f"{title}\n\n{content}"
    toxicity_scores = await analyze_content_toxicity(full_text)
    return determine_moderation_status(toxicity_scores, "post")

def should_auto_approve(moderation_result: ModerationResult) -> bool:
    """Check if content should be automatically approved"""
    return moderation_result.status == ModerationStatus.APPROVED

def should_auto_reject(moderation_result: ModerationResult) -> bool:
    """Check if content should be automatically rejected"""
    return moderation_result.status == ModerationStatus.REJECTED

def needs_manual_review(moderation_result: ModerationResult) -> bool:
    """Check if content needs manual review"""
    return moderation_result.status in [ModerationStatus.FLAGGED, ModerationStatus.PENDING]

# Romanian-specific content filtering (can be expanded)
ROMANIAN_PROFANITY_PATTERNS = [
    # Add Romanian-specific profanity patterns here if needed
    # This is a basic example - you might want to expand this
]

def contains_romanian_profanity(text: str) -> bool:
    """
    Check for Romanian-specific profanity patterns
    This is a basic implementation that can be expanded
    """
    text_lower = text.lower()
    for pattern in ROMANIAN_PROFANITY_PATTERNS:
        if pattern in text_lower:
            return True
    return False