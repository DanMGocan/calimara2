import os
import logging
import json
from typing import Dict, Tuple, Optional
from enum import Enum
import google.generativeai as genai
from sqlalchemy.orm import Session

# Load environment variables first
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# Configuration from environment (after loading .env)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
MODERATION_ENABLED = os.getenv("MODERATION_ENABLED", "True").lower() == "true"
TOXICITY_THRESHOLD_FLAG = float(os.getenv("TOXICITY_THRESHOLD_AUTO_APPROVE", "0.2"))  # Flag for review above this
TOXICITY_THRESHOLD_AUTO_REJECT = float(os.getenv("TOXICITY_THRESHOLD_AUTO_REJECT", "0.8"))  # Not used - AI never auto-rejects
ROMANIAN_CONTEXT_AWARE = os.getenv("ROMANIAN_CONTEXT_AWARE", "True").lower() == "true"

# Initialize Gemini
logger.info(f"Initializing Gemini... API_KEY exists: {bool(GEMINI_API_KEY)}, MODERATION_ENABLED: {MODERATION_ENABLED}")
logger.info(f"API_KEY value (first 10 chars): {GEMINI_API_KEY[:10] if GEMINI_API_KEY else 'NONE'}")
logger.info(f"MODEL: {GEMINI_MODEL}")

# Debug: Print all environment variables that start with GEMINI or contain KEY
import os
logger.info("Environment variables containing 'GEMINI' or 'KEY':")
for key, value in os.environ.items():
    if 'GEMINI' in key or 'KEY' in key:
        display_value = value[:10] + "..." if len(value) > 10 else value
        logger.info(f"  {key} = {display_value}")

if GEMINI_API_KEY and MODERATION_ENABLED:
    try:
        logger.info("Configuring Gemini API...")
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("Gemini API configured successfully for content moderation")
    except Exception as e:
        logger.error(f"Failed to configure Gemini API: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
else:
    if not GEMINI_API_KEY:
        logger.warning("Gemini API key not provided - moderation will be disabled")
    if not MODERATION_ENABLED:
        logger.warning("Moderation is disabled in configuration")

class ModerationStatus(str, Enum):
    APPROVED = "approved"
    PENDING = "pending"
    REJECTED = "rejected"
    FLAGGED = "flagged"

class ModerationResult:
    def __init__(self, status: ModerationStatus, toxicity_score: float, reason: str, details: Optional[Dict] = None):
        self.status = status
        self.toxicity_score = toxicity_score
        self.reason = reason
        self.details = details or {}

# Romanian-specific moderation prompts
ROMANIAN_CONTENT_MODERATION_PROMPT = """
Ești un moderator de conținut specializat pentru o platformă românească de literatură și microblogging. 
Analizează următorul text românesc și evaluează-l pentru:

1. TOXICITATE (0.0-1.0): Limbaj ofensator, insultător sau dăunător
2. HARASSMENT (0.0-1.0): Hărțuire, intimidare sau atacuri personale
3. HATE_SPEECH (0.0-1.0): Discurs de ură bazat pe etnie, religie, orientare sexuală, etc.
4. SEXUALLY_EXPLICIT (0.0-1.0): Conținut sexual explicit neadecvat
5. DANGEROUS_CONTENT (0.0-1.0): Conținut care promovează violența sau activități periculoase
6. ROMANIAN_PROFANITY (0.0-1.0): Înjurături și limbaj vulgar specific românesc

Ia în considerare:
- Contextul literar și artistic (poezie, proză, teatru)
- Nuanțele culturale românești
- Diferența între exprimarea artistică și atacurile personale
- Sarcasmul și umorul românesc
- Expresiile idiomatice românești

Returnează doar un JSON valid cu acest format:
{
    "toxicity": 0.0,
    "harassment": 0.0, 
    "hate_speech": 0.0,
    "sexually_explicit": 0.0,
    "dangerous_content": 0.0,
    "romanian_profanity": 0.0,
    "overall_assessment": "safe|review|unsafe",
    "reason": "Explicație scurtă în română",
    "literary_context": "considerare pentru contextul literar dacă e cazul"
}

Text de analizat:
"""

ENGLISH_FALLBACK_PROMPT = """
You are a content moderator for a Romanian literature and microblogging platform.
Analyze the following text and evaluate it for:

1. TOXICITY (0.0-1.0): Offensive, insulting, or harmful language
2. HARASSMENT (0.0-1.0): Harassment, intimidation, or personal attacks  
3. HATE_SPEECH (0.0-1.0): Hate speech based on ethnicity, religion, sexual orientation, etc.
4. SEXUALLY_EXPLICIT (0.0-1.0): Inappropriate sexually explicit content
5. DANGEROUS_CONTENT (0.0-1.0): Content promoting violence or dangerous activities

Consider:
- Literary and artistic context (poetry, prose, theater)
- Difference between artistic expression and personal attacks
- Sarcasm and humor
- Idiomatic expressions

Return only a valid JSON with this format:
{
    "toxicity": 0.0,
    "harassment": 0.0,
    "hate_speech": 0.0, 
    "sexually_explicit": 0.0,
    "dangerous_content": 0.0,
    "overall_assessment": "safe|review|unsafe",
    "reason": "Brief explanation",
    "literary_context": "consideration for literary context if applicable"
}

Text to analyze:
"""

def analyze_content_with_gemini(text: str, use_romanian_context: bool = True) -> Dict[str, float]:
    """
    Analyze text using Gemini with Romanian-aware prompts
    Returns toxicity scores for different categories
    """
    if not GEMINI_API_KEY or not MODERATION_ENABLED:
        logger.warning(f"Gemini not configured or moderation disabled. API_KEY exists: {bool(GEMINI_API_KEY)}, MODERATION_ENABLED: {MODERATION_ENABLED}")
        return {"toxicity": 0.0, "overall_assessment": "safe", "reason": "Moderation disabled or not configured"}
    
    logger.info(f"Starting Gemini content analysis for text: {text[:100]}...")
    
    try:
        # Choose appropriate prompt based on context awareness setting
        if use_romanian_context and ROMANIAN_CONTEXT_AWARE:
            prompt = ROMANIAN_CONTENT_MODERATION_PROMPT + text
        else:
            prompt = ENGLISH_FALLBACK_PROMPT + text
        
        # Create the model
        model = genai.GenerativeModel(GEMINI_MODEL)
        
        # Configure generation settings
        generation_config = genai.types.GenerationConfig(
            temperature=0.0,  # Deterministic for content moderation
            max_output_tokens=1024,
        )
        
        # Configure safety settings to allow analysis of potentially harmful content
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        logger.info(f"Calling Gemini API with model: {GEMINI_MODEL}")
        
        try:
            # Generate content with safety settings
            response = model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            logger.info("Gemini API call successful")
        except Exception as safety_error:
            # If safety settings fail, try without them
            logger.warning(f"Safety settings failed: {safety_error}, trying without safety settings")
            response = model.generate_content(
                prompt,
                generation_config=generation_config
            )
        
        # Check if response was blocked by safety filters
        if not response.text or response.text.strip() == "":
            logger.warning("Gemini response was empty, possibly blocked by safety filters")
            # For blocked content, assume it's toxic and needs review
            return {
                "toxicity": 0.7, 
                "harassment": 0.7,
                "hate_speech": 0.0,
                "sexually_explicit": 0.0,
                "dangerous_content": 0.0,
                "romanian_profanity": 0.0,
                "overall_assessment": "review", 
                "reason": "Content blocked by safety filters - flagged for manual review"
            }
        
        # Parse the JSON response
        response_text = response.text.strip()
        
        # Clean response text if it contains markdown code blocks
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        try:
            scores = json.loads(response_text)
            logger.info(f"Gemini moderation analysis completed. Toxicity: {scores.get('toxicity', 0.0):.3f}")
            return scores
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini JSON response: {e}. Response: {response_text[:200]}...")
            # Fallback to safe assessment
            return {"toxicity": 0.0, "overall_assessment": "safe", "reason": "Parsing error - defaulting to safe"}
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error calling Gemini API: {e}")
        
        # If it's a safety filter error, flag for manual review
        if "HARM_CATEGORY" in error_msg or "SAFETY" in error_msg.upper():
            logger.warning(f"Gemini safety filter triggered: {error_msg}")
            return {
                "toxicity": 1.0, 
                "harassment": 1.0,
                "hate_speech": 0.0,
                "sexually_explicit": 0.0,
                "dangerous_content": 0.0,
                "romanian_profanity": 0.0,
                "overall_assessment": "review", 
                "reason": f"Blocked by Gemini safety filters ({error_msg}) - requires manual review"
            }
        
        # For other API errors, fail safe - approve
        return {"toxicity": 0.0, "overall_assessment": "safe", "reason": f"API error ({error_msg}) - defaulting to safe"}

def determine_moderation_status(gemini_scores: Dict[str, float], content_type: str = "comment") -> ModerationResult:
    """
    Determine moderation status based on Gemini analysis scores
    AI NEVER auto-rejects content - only flags for human review or approves
    """
    toxicity = gemini_scores.get("toxicity", 0.0)
    harassment = gemini_scores.get("harassment", 0.0)
    hate_speech = gemini_scores.get("hate_speech", 0.0)
    sexually_explicit = gemini_scores.get("sexually_explicit", 0.0)
    dangerous_content = gemini_scores.get("dangerous_content", 0.0)
    romanian_profanity = gemini_scores.get("romanian_profanity", 0.0)
    overall_assessment = gemini_scores.get("overall_assessment", "safe")
    reason = gemini_scores.get("reason", "Automated moderation")
    
    # Calculate maximum toxicity across all categories
    max_toxicity = max(toxicity, harassment, hate_speech, sexually_explicit, dangerous_content, romanian_profanity)
    
    # AI never auto-rejects - only flags for human review if toxic
    if overall_assessment == "unsafe" or max_toxicity > TOXICITY_THRESHOLD_FLAG:
        return ModerationResult(
            status=ModerationStatus.FLAGGED,
            toxicity_score=max_toxicity,
            reason=f"High toxicity detected - requires human review (score: {max_toxicity:.2f}): {reason}",
            details=gemini_scores
        )
    elif overall_assessment == "review":
        return ModerationResult(
            status=ModerationStatus.FLAGGED,
            toxicity_score=max_toxicity,
            reason=f"Content flagged for manual review: {reason}",
            details=gemini_scores
        )
    
    # Auto-approve for low toxicity
    return ModerationResult(
        status=ModerationStatus.APPROVED,
        toxicity_score=max_toxicity,
        reason=f"Content approved - low toxicity (score: {max_toxicity:.2f}): {reason}",
        details=gemini_scores
    )

async def moderate_comment(content: str) -> ModerationResult:
    """
    Analyze and moderate a comment using Gemini 1.5 Flash
    """
    logger.info(f"Starting comment moderation for content: {content[:50]}...")
    
    if not MODERATION_ENABLED:
        logger.info("Moderation disabled - auto-approving comment")
        return ModerationResult(
            status=ModerationStatus.APPROVED,
            toxicity_score=0.0,
            reason="Moderation disabled"
        )
    
    if not GEMINI_API_KEY:
        logger.warning("Gemini API key not configured - auto-approving comment")
        return ModerationResult(
            status=ModerationStatus.APPROVED,
            toxicity_score=0.0,
            reason="Gemini API key not available"
        )
    
    try:
        gemini_scores = analyze_content_with_gemini(content)
        logger.info(f"Gemini analysis for comment: {gemini_scores}")
        result = determine_moderation_status(gemini_scores, "comment")
        logger.info(f"Comment moderation result: {result.status.value} (score: {result.toxicity_score:.3f})")
        return result
    except Exception as e:
        logger.error(f"Error in comment moderation: {e}")
        # Fail safe - approve on error but log it
        return ModerationResult(
            status=ModerationStatus.APPROVED,
            toxicity_score=0.0,
            reason=f"Moderation error: {str(e)}"
        )

async def moderate_post(title: str, content: str) -> ModerationResult:
    """
    Analyze and moderate a post (title + content) using Gemini 1.5 Flash
    """
    logger.info(f"Starting post moderation for title: {title[:30]}...")
    
    if not MODERATION_ENABLED:
        logger.info("Moderation disabled - auto-approving post")
        return ModerationResult(
            status=ModerationStatus.APPROVED,
            toxicity_score=0.0,
            reason="Moderation disabled"
        )
    
    if not GEMINI_API_KEY:
        logger.warning("Gemini API key not configured - auto-approving post")
        return ModerationResult(
            status=ModerationStatus.APPROVED,
            toxicity_score=0.0,
            reason="Gemini API key not available"
        )
    
    try:
        # Combine title and content for analysis
        full_text = f"Titlu: {title}\n\nConținut: {content}"
        gemini_scores = analyze_content_with_gemini(full_text)
        logger.info(f"Gemini analysis for post: {gemini_scores}")
        result = determine_moderation_status(gemini_scores, "post")
        logger.info(f"Post moderation result: {result.status.value} (score: {result.toxicity_score:.3f})")
        return result
    except Exception as e:
        logger.error(f"Error in post moderation: {e}")
        # Fail safe - approve on error but log it
        return ModerationResult(
            status=ModerationStatus.APPROVED,
            toxicity_score=0.0,
            reason=f"Moderation error: {str(e)}"
        )

def should_auto_approve(moderation_result: ModerationResult) -> bool:
    """Check if content should be automatically approved"""
    return moderation_result.status == ModerationStatus.APPROVED

def should_auto_reject(moderation_result: ModerationResult) -> bool:
    """Check if content should be automatically rejected"""
    return moderation_result.status == ModerationStatus.REJECTED

def needs_manual_review(moderation_result: ModerationResult) -> bool:
    """Check if content needs manual review"""
    return moderation_result.status in [ModerationStatus.FLAGGED, ModerationStatus.PENDING]

# Romanian-specific content patterns for enhanced detection
ROMANIAN_PROFANITY_PATTERNS = [
    # Common Romanian profanity - add more as needed
    "pula", "muie", "futut", "cacat", "nenorocit", "jegos", "curve", "pizda",
    "dracu", "mortii", "naiba", "dumnezeu", "ma-ta", "ma-tii", "pu[șs]a",
    "idiot", "prost", "tâmpit", "retardat", "debil", "cretin"
]

ROMANIAN_HATE_SPEECH_PATTERNS = [
    # Romanian hate speech patterns - cultural context aware
    "țigan", "cioară", "jidan", "evreu de căcat", "ungur", "secui",
    "musulman", "turc", "rus", "bulgar", "sârb"
]

def contains_romanian_profanity(text: str) -> Tuple[bool, float]:
    """
    Enhanced Romanian-specific profanity detection
    Returns (has_profanity, severity_score)
    """
    text_lower = text.lower()
    profanity_count = 0
    total_words = len(text.split())
    
    for pattern in ROMANIAN_PROFANITY_PATTERNS:
        if pattern in text_lower:
            profanity_count += text_lower.count(pattern)
    
    if profanity_count == 0:
        return False, 0.0
    
    # Calculate severity based on frequency relative to text length
    severity = min(1.0, profanity_count / max(1, total_words) * 10)
    return True, severity

def contains_romanian_hate_speech(text: str) -> Tuple[bool, float]:
    """
    Enhanced Romanian-specific hate speech detection
    Returns (has_hate_speech, severity_score)
    """
    text_lower = text.lower()
    hate_count = 0
    
    for pattern in ROMANIAN_HATE_SPEECH_PATTERNS:
        if pattern in text_lower:
            hate_count += text_lower.count(pattern)
    
    if hate_count == 0:
        return False, 0.0
    
    # Hate speech is always high severity when detected
    severity = min(1.0, hate_count * 0.8)
    return True, severity

async def enhanced_romanian_analysis(text: str) -> Dict[str, float]:
    """
    Combine Gemini analysis with Romanian-specific pattern detection
    """
    # Get base analysis from Gemini
    gemini_scores = analyze_content_with_gemini(text)
    
    # Enhance with Romanian-specific detection
    has_profanity, profanity_score = contains_romanian_profanity(text)
    has_hate_speech, hate_score = contains_romanian_hate_speech(text)
    
    # Combine scores (take maximum to be conservative)
    enhanced_scores = gemini_scores.copy()
    enhanced_scores["romanian_profanity"] = max(
        gemini_scores.get("romanian_profanity", 0.0), 
        profanity_score
    )
    enhanced_scores["hate_speech"] = max(
        gemini_scores.get("hate_speech", 0.0), 
        hate_score
    )
    
    # Update overall toxicity if local patterns detected severe issues
    if has_profanity or has_hate_speech:
        enhanced_scores["toxicity"] = max(
            enhanced_scores.get("toxicity", 0.0),
            max(profanity_score, hate_score)
        )
    
    logger.info(f"Enhanced Romanian analysis: Gemini toxicity: {gemini_scores.get('toxicity', 0.0):.3f}, "
                f"Romanian patterns: profanity={profanity_score:.3f}, hate={hate_score:.3f}")
    
    return enhanced_scores

def log_moderation_decision(
    db: Session,
    content_type: str,
    content_id: int,
    user_id: Optional[int],
    moderation_result: ModerationResult
) -> None:
    """
    Log AI moderation decision to database for tracking and review
    """
    try:
        from .models import ModerationLog
        
        # Extract detailed scores from moderation result
        details = moderation_result.details or {}
        
        log_entry = ModerationLog(
            content_type=content_type,
            content_id=content_id,
            user_id=user_id,
            ai_decision=moderation_result.status.value,
            toxicity_score=moderation_result.toxicity_score,
            harassment_score=details.get("harassment", 0.0),
            hate_speech_score=details.get("hate_speech", 0.0),
            sexually_explicit_score=details.get("sexually_explicit", 0.0),
            dangerous_content_score=details.get("dangerous_content", 0.0),
            romanian_profanity_score=details.get("romanian_profanity", 0.0),
            ai_reason=moderation_result.reason,
            ai_details=json.dumps(details) if details else None,
            human_decision="pending" if moderation_result.status == ModerationStatus.FLAGGED else None
        )
        
        db.add(log_entry)
        # Note: Don't commit here - let the calling function handle the transaction
        
        logger.info(f"Logged moderation decision for {content_type} {content_id}: {moderation_result.status.value}")
        
    except Exception as e:
        logger.error(f"Failed to log moderation decision: {e}")
        # Rollback the session to prevent transaction issues
        try:
            db.rollback()
        except Exception:
            pass
        # Don't raise - logging failures shouldn't block content processing

async def moderate_comment_with_logging(content: str, comment_id: int, user_id: Optional[int], db: Session) -> ModerationResult:
    """
    Moderate a comment and log the decision to database
    """
    logger.info(f"moderate_comment_with_logging called for comment {comment_id}")
    
    # First do the AI moderation
    result = await moderate_comment(content)
    logger.info(f"AI moderation completed for comment {comment_id}: {result.status.value}")
    
    # Then try to log it (but don't fail if logging fails)
    try:
        log_moderation_decision(db, "comment", comment_id, user_id, result)
        logger.info(f"Successfully logged moderation decision for comment {comment_id}")
    except Exception as e:
        logger.error(f"Failed to log moderation decision for comment {comment_id}: {e}")
        # Continue anyway - logging failure shouldn't break moderation
    
    return result

async def moderate_post_with_logging(title: str, content: str, post_id: int, user_id: int, db: Session) -> ModerationResult:
    """
    Moderate a post and log the decision to database
    """
    logger.info(f"moderate_post_with_logging called for post {post_id}")
    
    # First do the AI moderation  
    result = await moderate_post(title, content)
    logger.info(f"AI moderation completed for post {post_id}: {result.status.value}")
    
    # Then try to log it (but don't fail if logging fails)
    try:
        log_moderation_decision(db, "post", post_id, user_id, result)
        logger.info(f"Successfully logged moderation decision for post {post_id}")
    except Exception as e:
        logger.error(f"Failed to log moderation decision for post {post_id}: {e}")
        # Continue anyway - logging failure shouldn't break moderation
    
    return result

async def test_ai_moderation() -> dict:
    """
    Test function to check if AI moderation is working
    """
    logger.info("=== STARTING AI MODERATION DIAGNOSTIC ===")
    
    # Check configuration
    logger.info(f"MODERATION_ENABLED: {MODERATION_ENABLED}")
    logger.info(f"GEMINI_API_KEY exists: {bool(GEMINI_API_KEY)}")
    logger.info(f"GEMINI_MODEL: {GEMINI_MODEL}")
    logger.info(f"TOXICITY_THRESHOLD_FLAG: {TOXICITY_THRESHOLD_FLAG}")
    logger.info(f"Gemini API configured: {bool(GEMINI_API_KEY)}")
    
    if not MODERATION_ENABLED:
        return {"error": "Moderation is disabled", "ai_working": False}
    
    if not GEMINI_API_KEY:
        return {"error": "Gemini API key not configured", "ai_working": False}
    
    test_toxic_content = "Du-te dracului, ești un idiot și îți doresc să mori!"
    test_normal_content = "Aceasta este o poezie frumoasă despre natura din România."
    
    logger.info("Testing AI moderation...")
    
    try:
        # Test toxic content
        logger.info("Testing toxic content...")
        toxic_result = await moderate_comment(test_toxic_content)
        logger.info(f"Toxic test result: {toxic_result.status.value}, score: {toxic_result.toxicity_score}")
        
        # Test normal content  
        logger.info("Testing normal content...")
        normal_result = await moderate_comment(test_normal_content)
        logger.info(f"Normal test result: {normal_result.status.value}, score: {normal_result.toxicity_score}")
        
        return {
            "configuration": {
                "moderation_enabled": MODERATION_ENABLED,
                "gemini_api_key_exists": bool(GEMINI_API_KEY),
                "gemini_model": GEMINI_MODEL,
                "toxicity_threshold": TOXICITY_THRESHOLD_FLAG,
                "api_configured": bool(GEMINI_API_KEY)
            },
            "toxic_content": {
                "status": toxic_result.status.value,
                "score": toxic_result.toxicity_score,
                "reason": toxic_result.reason
            },
            "normal_content": {
                "status": normal_result.status.value,
                "score": normal_result.toxicity_score,
                "reason": normal_result.reason
            },
            "ai_working": True
        }
        
    except Exception as e:
        logger.error(f"AI moderation test failed: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "ai_working": False
        }