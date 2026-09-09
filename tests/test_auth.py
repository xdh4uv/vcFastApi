"""Offline regressions: python -m unittest discover -s tests -v.

SQLite supplies disposable storage; PostgreSQL schema SQL is checked separately.
No test connects to the configured application database or Google.
"""
import importlib
import os
import unittest
from datetime import timedelta
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "local-regression-test-secret"

from fastapi import HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import DefaultClause, MetaData, create_engine, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.security import create_access_token, get_current_user
from app.models.usersModel import User
from app.routers import auth, profile
from app.schemas.schemas import GoogleLoginIn, ProfileUpdate, UserCreate


def create_test_engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool, execution_options={"schema_translate_map": {"public": None}},
    )
    metadata = MetaData()
    table = User.__table__.to_metadata(metadata)
    # SQLite does not coerce the quoted PostgreSQL boolean default to false.
    table.c.onboarding_completed.server_default = DefaultClause(text("false"))
    metadata.create_all(engine)
    return engine


class AuthRegressionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_test_engine()
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def signup(self, username="student"):
        return auth.signup(UserCreate(
            email=f"{username}@example.com", username=username, password="test-password-123",
        ), self.db)

    def login(self, email="student@example.com", password="test-password-123"):
        return auth.login(OAuth2PasswordRequestForm(username=email, password=password), self.db)

    def assert_status(self, expected, call):
        with self.assertRaises(HTTPException) as caught:
            call()
        self.assertEqual(caught.exception.status_code, expected)

    def test_signup_login_and_current_user(self):
        created = self.signup()
        self.assertNotEqual(created.hashed_password, "test-password-123")
        self.assertFalse(created.onboarding_completed)
        token = self.login().access_token
        current = get_current_user(token, self.db)
        self.assertEqual(auth.me(current).id, created.id)
        self.assertEqual(profile.get_me(current).email, "student@example.com")

    def test_duplicate_signup_is_conflict(self):
        self.signup()
        self.assert_status(409, self.signup)

    def test_wrong_password_and_unknown_user_are_unauthorized(self):
        self.signup()
        self.assert_status(401, lambda: self.login(password="incorrect"))
        self.assert_status(401, lambda: self.login(email="unknown@example.com"))

    def test_expired_and_invalid_tokens_are_unauthorized(self):
        user = self.signup()
        expired = create_access_token(str(user.id), timedelta(seconds=-1))
        self.assert_status(401, lambda: get_current_user(expired, self.db))
        self.assert_status(401, lambda: get_current_user("invalid", self.db))

    def test_profile_username_update_and_conflict(self):
        user = self.signup()
        self.signup("other")
        updated = profile.update_me(ProfileUpdate(username="renamed"), self.db, user)
        self.assertEqual(updated.username, "renamed")
        self.assert_status(409, lambda: profile.update_me(
            ProfileUpdate(username="other"), self.db, user,
        ))

    def test_google_login_creates_account_and_reuses_it(self):
        claims = {"sub": "google-test-id", "email": "google@example.com", "email_verified": True}
        with patch.object(auth.settings, "google_client_id", "test-client"), patch.object(
            auth.google_id_token, "verify_oauth2_token", return_value=claims,
        ):
            first = auth.google_login(GoogleLoginIn(credential="test-only"), self.db)
            second = auth.google_login(GoogleLoginIn(credential="test-only"), self.db)
        self.assertEqual(get_current_user(first.access_token, self.db).id,
                         get_current_user(second.access_token, self.db).id)
        self.assertEqual(self.db.query(User).count(), 1)
        self.assert_status(401, lambda: self.login(email="google@example.com"))

    def test_postgres_queries_target_existing_public_users(self):
        sql = str(select(User).compile(dialect=postgresql.dialect()))
        self.assertIn("FROM public.users", sql)

    def test_startup_initializes_public_users_only(self):
        with patch.object(Base.metadata, "create_all") as create_all:
            importlib.import_module("app.main")
        self.assertEqual([table.fullname for table in create_all.call_args.kwargs["tables"]],
                         ["public.users"])


if __name__ == "__main__":
    unittest.main()
