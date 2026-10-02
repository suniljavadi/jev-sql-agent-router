from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Customer


def seed(session: Session) -> None:
    if session.scalar(select(func.count()).select_from(Customer)):
        return
    session.add_all([
        Customer(name="Acme Corp", region="East", revenue=120000),
        Customer(name="Northwind", region="West", revenue=84000),
        Customer(name="Globex", region="East", revenue=156000),
    ])
    session.commit()