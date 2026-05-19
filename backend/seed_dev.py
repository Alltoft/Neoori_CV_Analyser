"""
Dev/test seed script — idempotent.

Creates default test accounts if they don't exist, or resets their passwords.
Run from /backend:  python seed_dev.py

DEFAULT CREDENTIALS
-------------------
admin@neoori.dev   admin1234   role=admin
"""
from app import create_app
from app.extensions import db, bcrypt
from app.models.user import User

ACCOUNTS = [
    dict(email="admin@neoori.dev", password="admin1234", role="admin",  plan="free"),
]

app = create_app()
with app.app_context():
    for spec in ACCOUNTS:
        user = User.query.filter_by(email=spec["email"]).first()
        pw_hash = bcrypt.generate_password_hash(spec["password"]).decode("utf-8")
        if user:
            user.password_hash = pw_hash
            print(f"[reset]  {spec['email']}  →  {spec['password']}")
        else:
            user = User(
                email=spec["email"],
                password_hash=pw_hash,
                role=spec["role"],
                plan=spec["plan"],
            )
            db.session.add(user)
            print(f"[create] {spec['email']}  →  {spec['password']}")
    db.session.commit()
    print("Done.")
