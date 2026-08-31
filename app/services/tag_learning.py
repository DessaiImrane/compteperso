from app.models import Tag, TagLearning


def normalize_libelle(s: str) -> str:
    return s.strip().lower()


def suggest_tags(db, libelle: str) -> list[Tag]:
    key = normalize_libelle(libelle)
    learnings = db.query(TagLearning).filter_by(libelle_pattern=key).all()
    return [learning.tag for learning in learnings]


def record_learning(db, libelle: str, tags: list[Tag]) -> None:
    key = normalize_libelle(libelle)
    for tag in tags:
        exists = db.query(TagLearning).filter_by(libelle_pattern=key, tag_id=tag.id).first()
        if not exists:
            db.add(TagLearning(libelle_pattern=key, tag_id=tag.id))
    db.commit()
