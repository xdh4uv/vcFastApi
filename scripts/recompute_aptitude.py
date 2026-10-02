"""Run nightly via the repository scheduler or operator CLI. No model calls."""
from app.core.database import SessionLocal
from app.core.config import settings
from app.services.aptitude import recompute_all


def main():
    if not settings.engagement_enabled:
        raise SystemExit('Enable ENGAGEMENT_ENABLED after migrations V4–V6.')
    with SessionLocal() as db:
        print(f'Recomputed {recompute_all(db)} course profiles.')


if __name__ == '__main__':
    main()
