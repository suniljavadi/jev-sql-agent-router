from sqlalchemy.orm import Session

from app.db.database import engine
from app.db.migrations import upgrade_database
from app.db.seed import seed


def main() -> None:
    upgrade_database()
    with Session(engine) as session:
        seed(session)
    print("Sample customers seeded")


if __name__ == "__main__":
    main()