#!/usr/bin/env python3
"""
Test script to verify AI moderation is working
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

# Import after loading env vars
from app import moderation

async def test_moderation():
    print("=" * 60)
    print("TESTING AI MODERATION")
    print("=" * 60)
    
    # Check configuration
    print(f"\nConfiguration:")
    print(f"- MODERATION_ENABLED: {moderation.MODERATION_ENABLED}")
    print(f"- GEMINI_API_KEY exists: {bool(moderation.GEMINI_API_KEY)}")
    print(f"- GEMINI_MODEL: {moderation.GEMINI_MODEL}")
    print(f"- TOXICITY_THRESHOLD_FLAG: {moderation.TOXICITY_THRESHOLD_FLAG}")
    
    # Test cases
    test_cases = [
        {
            "text": "Du-te dracului, ești un idiot și îți doresc să mori!",
            "expected": "flagged",
            "type": "toxic"
        },
        {
            "text": "Aceasta este o poezie frumoasă despre natura din România.",
            "expected": "approved",
            "type": "normal"
        },
        {
            "text": "Ești o curvă jegoasă și ar trebui să dispari!",
            "expected": "flagged",
            "type": "hate speech"
        },
        {
            "text": "Mulțumesc pentru articol, foarte informativ!",
            "expected": "approved",
            "type": "positive"
        }
    ]
    
    print(f"\nTesting {len(test_cases)} cases...")
    print("-" * 60)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['type']}")
        print(f"Text: {test_case['text'][:50]}...")
        
        try:
            # Test as comment
            result = await moderation.moderate_comment(test_case['text'])
            
            print(f"Result: {result.status.value}")
            print(f"Score: {result.toxicity_score:.3f}")
            print(f"Reason: {result.reason}")
            
            if result.status.value == test_case['expected']:
                print("✅ PASS - Expected result")
            else:
                print(f"❌ FAIL - Expected {test_case['expected']}, got {result.status.value}")
                
        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Testing complete!")
    
    # Test the direct Gemini API call
    print("\n" + "=" * 60)
    print("TESTING DIRECT GEMINI API CALL")
    print("=" * 60)
    
    try:
        toxic_text = "Ești un prost și un idiot!"
        print(f"\nAnalyzing: {toxic_text}")
        
        scores = moderation.analyze_content_with_gemini(toxic_text)
        print(f"Gemini response: {scores}")
        
    except Exception as e:
        print(f"❌ Direct API call failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_moderation())