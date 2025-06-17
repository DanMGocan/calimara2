import os
import logging
import json
from typing import Dict, Tuple, Optional
from enum import Enum
from google import genai

logger = logging.getLogger(__name__)

# Configuration from environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
MODERATION_ENABLED = os.getenv("MODERATION_ENABLED", "True").lower() == "true"
TOXICITY_THRESHOLD_AUTO_APPROVE = float(os.getenv("TOXICITY_THRESHOLD_AUTO_APPROVE", "0.3"))
TOXICITY_THRESHOLD_AUTO_REJECT = float(os.getenv("TOXICITY_THRESHOLD_AUTO_REJECT", "0.8"))
ROMANIAN_CONTEXT_AWARE = os.getenv("ROMANIAN_CONTEXT_AWARE", "True").lower() == "true"

# Initialize Gemini client
gemini_client = None
if GEMINI_API_KEY and MODERATION_ENABLED:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Gemini client initialized successfully for content moderation")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini client: {e}")

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

async def analyze_content_with_gemini(text: str, use_romanian_context: bool = True) -> Dict[str, float]:
    """
    Analyze text using Gemini 1.5 Flash with Romanian-aware prompts
    Returns toxicity scores for different categories
    """
    if not gemini_client or not MODERATION_ENABLED:
        logger.warning("Gemini client not configured or moderation disabled")
        return {"toxicity": 0.0, "overall_assessment": "safe"}
    
    try:
        # Choose appropriate prompt based on context awareness setting
        if use_romanian_context and ROMANIAN_CONTEXT_AWARE:
            prompt = ROMANIAN_CONTENT_MODERATION_PROMPT + text
        else:
            prompt = ENGLISH_FALLBACK_PROMPT + text
        
        # Try different approaches for safety settings with Gemini 2.0
        try:
            # First try with minimal safety settings
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=0.0,  # Deterministic for content moderation
                    max_output_tokens=1024,
                    safety_settings={
                        genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                        genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_NONE,
                        genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                        genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_NONE
                    }
                )
            )
        except Exception as safety_error:
            # If safety settings fail, try without them
            logger.warning(f"Safety settings failed: {safety_error}, trying without safety settings")
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=1024
                )
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
        if "HARM_CATEGORY" in error_msg:
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
    if overall_assessment == "unsafe" or max_toxicity >= TOXICITY_THRESHOLD_AUTO_APPROVE:
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
    
    if not gemini_client:
        logger.warning("Gemini client not initialized - auto-approving comment")
        return ModerationResult(
            status=ModerationStatus.APPROVED,
            toxicity_score=0.0,
            reason="Gemini client not available"
        )
    
    gemini_scores = await analyze_content_with_gemini(content)
    result = determine_moderation_status(gemini_scores, "comment")
    logger.info(f"Comment moderation result: {result.status.value} (score: {result.toxicity_score:.3f})")
    return result

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
    
    if not gemini_client:
        logger.warning("Gemini client not initialized - auto-approving post")
        return ModerationResult(
            status=ModerationStatus.APPROVED,
            toxicity_score=0.0,
            reason="Gemini client not available"
        )
    
    # Combine title and content for analysis
    full_text = f"Titlu: {title}\n\nConținut: {content}"
    gemini_scores = await analyze_content_with_gemini(full_text)
    result = determine_moderation_status(gemini_scores, "post")
    logger.info(f"Post moderation result: {result.status.value} (score: {result.toxicity_score:.3f})")
    return result

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
    gemini_scores = await analyze_content_with_gemini(text)
    
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