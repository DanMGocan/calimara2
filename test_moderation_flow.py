#!/usr/bin/env python3
"""
Test the complete moderation flow: create flagged content and check if it appears in queue
"""

import os
import sys
import asyncio
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

# Import after loading env vars
from app import models, crud, moderation
from app.database import get_db

# Create database session for testing
DATABASE_URL = f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}@{os.getenv('MYSQL_HOST')}/{os.getenv('MYSQL_DATABASE')}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

async def test_moderation_flow():
    print("=" * 60)
    print("TESTING COMPLETE MODERATION FLOW")
    print("=" * 60)
    
    db = SessionLocal()
    
    try:
        # 1. Get a test user (the test user from schema.sql)
        test_user = db.query(models.User).filter(models.User.email == "sad@sad.sad").first()
        if not test_user:
            print("❌ Test user not found. Please run initdb.py first.")
            return
        
        print(f"✅ Found test user: {test_user.username}")
        
        # 2. Create a toxic comment that should be flagged
        toxic_comment_content = "Ești un idiot și un prost! Du-te naibii!"
        print(f"\n2. Creating toxic comment: '{toxic_comment_content}'")
        
        # Get a post to comment on
        test_post = db.query(models.Post).first()
        if not test_post:
            print("❌ No posts found. Please create a post first.")
            return
        
        print(f"   Commenting on post: {test_post.title}")
        
        # Create the comment
        from app.schemas import CommentCreate
        comment_data = CommentCreate(
            content=toxic_comment_content,
            author_name="Test User",
            author_email="test@example.com"
        )
        
        # Create comment in DB
        db_comment = crud.create_comment(db, comment_data, test_post.id, test_user.id)
        print(f"   ✅ Comment created with ID: {db_comment.id}")
        
        # Run moderation
        moderation_result = await moderation.moderate_comment_with_logging(
            toxic_comment_content, db_comment.id, test_user.id, db
        )
        
        # Update comment with moderation results
        db_comment.moderation_status = moderation_result.status.value
        db_comment.toxicity_score = moderation_result.toxicity_score
        db_comment.moderation_reason = moderation_result.reason
        db_comment.approved = moderation_result.status.value == "approved"
        
        db.commit()
        db.refresh(db_comment)
        
        print(f"   Moderation status: {db_comment.moderation_status}")
        print(f"   Toxicity score: {db_comment.toxicity_score:.3f}")
        print(f"   Approved: {db_comment.approved}")
        print(f"   Reason: {db_comment.moderation_reason}")
        
        # 3. Check if it appears in moderation queue
        print("\n3. Checking moderation queue...")
        
        # Get flagged comments
        flagged_comments = crud.get_comments_for_moderation(db, status_filter="flagged", limit=10)
        print(f"   Found {len(flagged_comments)} flagged comments")
        
        # Check if our comment is in the queue
        our_comment = next((c for c in flagged_comments if c.id == db_comment.id), None)
        if our_comment:
            print(f"   ✅ Our comment is in the flagged queue!")
        else:
            print(f"   ❌ Our comment is NOT in the flagged queue")
            
        # 4. Check moderation stats
        print("\n4. Checking moderation stats...")
        stats = crud.get_moderation_stats(db)
        print(f"   Comments flagged: {stats['comments_flagged']}")
        print(f"   Comments pending: {stats['comments_pending']}")
        print(f"   Comments approved: {stats['comments_approved']}")
        print(f"   Comments rejected: {stats['comments_rejected']}")
        
        # 5. Check moderation logs
        print("\n5. Checking moderation logs...")
        logs = db.query(models.ModerationLog).filter(
            models.ModerationLog.content_type == "comment",
            models.ModerationLog.content_id == db_comment.id
        ).all()
        
        print(f"   Found {len(logs)} moderation log entries for this comment")
        for log in logs:
            print(f"   - AI Decision: {log.ai_decision}")
            print(f"   - Toxicity Score: {log.toxicity_score:.3f}")
            print(f"   - Created: {log.created_at}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        db.close()
    
    print("\n" + "=" * 60)
    print("Test complete!")

if __name__ == "__main__":
    asyncio.run(test_moderation_flow())