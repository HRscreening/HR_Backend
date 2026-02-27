from sqlalchemy import (
    Column,
    BigInteger,
    DateTime,
    func,
    Identity,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TEXT
from configs.postgress_db import Base


class Waitlist(Base):
    __tablename__ = "waitlist"
    __table_args__ = (
        UniqueConstraint("email", name="waitlist_email_key"),
    )

    id = Column(
        BigInteger,
        Identity(always=False, start=1, increment=1),
        primary_key=True,
        autoincrement=True,
    )
    email = Column(TEXT, nullable=False, unique=True)
    first_name = Column(TEXT, nullable=False)
    last_name = Column(TEXT, nullable=False)
    company = Column(TEXT, nullable=False, server_default="''")
    company_size = Column(TEXT, nullable=False, server_default="''")
    monthly_hires = Column(TEXT, nullable=False, server_default="''")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=True,
    )
