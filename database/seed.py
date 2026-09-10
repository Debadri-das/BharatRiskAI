import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.database.connection import Base, SessionLocal, engine
from backend.database.seed_data import seed_demo


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_demo(db)
        print("Demo database seeded.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

