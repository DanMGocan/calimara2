from ._shared import *

def get_user_by_id(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def get_user_by_google_id(db: Session, google_id: str):
    return db.query(models.User).filter(models.User.google_id == google_id).first()

def create_user_from_google(db: Session, user_data: Dict[str, Any]):
    if "subtitle" in user_data:
        user_data = {
            **user_data,
            "subtitle": rich_text.sanitize_optional_rich_text(user_data.get("subtitle")),
        }
    db_user = models.User(**user_data)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, user_id: int, user_update: Dict[str, Any]):
    if "subtitle" in user_update:
        user_update = {
            **user_update,
            "subtitle": rich_text.sanitize_optional_rich_text(user_update.get("subtitle")),
        }
    db.query(models.User).filter(models.User.id == user_id).update(user_update)
    db.commit()
    return get_user_by_id(db, user_id)

def get_random_users(db: Session, limit: int = 10):
    return db.query(models.User).order_by(func.random()).limit(limit).all()

def get_random_user_with_posts(db: Session):
    # Postgres rejects `SELECT DISTINCT ... ORDER BY random()` because the
    # ORDER BY expression isn't in the SELECT list. Use EXISTS instead of
    # DISTINCT+JOIN so we can order by random() freely.
    return (
        db.query(models.User)
        .filter(
            db.query(models.Post.id)
            .filter(
                models.Post.user_id == models.User.id,
                models.Post.moderation_status == "approved",
            )
            .exists()
        )
        .order_by(func.random())
        .limit(1)
        .first()
    )

# ===================================
# POST CRUD FUNCTIONS
# ===================================
