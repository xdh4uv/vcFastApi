from sqlalchemy import Boolean, Column, Date, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from ..core.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "security"}

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(64), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)
    google_sub = Column(String(64), unique=True, index=True, nullable=True)

    full_name = Column(String(128), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(32), nullable=True)
    bio = Column(Text, nullable=True)
    phone_country_code = Column(String(8), nullable=True)
    phone_number = Column(String(32), nullable=True)
    avatar_url = Column(String(512), nullable=True)
    onboarding_completed = Column(Boolean, nullable=False, server_default="false")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
