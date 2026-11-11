import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Load .env from the same folder as this file, and let it override system variables
load_dotenv(Path(__file__).parent / ".env", override=True)

DATABASE_URL = os.getenv(
    "DATABASE_URL", "mysql+pymysql://root:@localhost:3306/tax_automation"
)

connect_args = {}
ca_file = Path(__file__).parent / "aiven_ca.pem"
if ca_file.exists() and "localhost" not in DATABASE_URL and "127.0.0.1" not in DATABASE_URL:
    connect_args["ssl_ca"] = str(ca_file)
    connect_args["ssl_verify_cert"] = True
    connect_args["ssl_verify_identity"] = True

engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()