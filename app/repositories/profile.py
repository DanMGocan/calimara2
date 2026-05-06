from ._shared import *

def get_featured_posts_for_user(db: Session, user_id: int):
    return db.query(models.FeaturedPost).options(joinedload(models.FeaturedPost.post)).filter(
        models.FeaturedPost.user_id == user_id
    ).order_by(models.FeaturedPost.position).all()

def get_best_friends_for_user(db: Session, user_id: int):
    return db.query(models.BestFriend).options(joinedload(models.BestFriend.friend)).filter(
        models.BestFriend.user_id == user_id
    ).order_by(models.BestFriend.position).all()

# ===================================
# AWARDS
# ===================================

def get_user_awards(db: Session, user_id: int):
    return db.query(models.UserAward).filter(models.UserAward.user_id == user_id).order_by(models.UserAward.award_date.desc()).all()


# ===================================
# GOLOGANI / SHOP
# ===================================
