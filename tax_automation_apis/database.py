import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Load .env from the same folder as this file without overriding system variables
load_dotenv(Path(__file__).parent / ".env", override=False)

DATABASE_URL = os.getenv(
    "DATABASE_URL", "mysql+pymysql://root:@localhost:3306/tax_automation"
)

connect_args = {}
if "localhost" not in DATABASE_URL and "127.0.0.1" not in DATABASE_URL:
    candidate_ca_paths = []
    if os.getenv("AIVEN_CA_PATH"):
        candidate_ca_paths.append(Path(os.getenv("AIVEN_CA_PATH")))
    candidate_ca_paths.extend([
        Path("/etc/secrets/aiven_ca.pem"),
        Path(__file__).parent / "aiven_ca.pem",
        Path.cwd() / "aiven_ca.pem",
    ])
    ca_file = next((p for p in candidate_ca_paths if p.exists()), None)
    if not ca_file:
        raise RuntimeError(
            "Aiven MySQL CA certificate is missing. Strict TLS verification requires a valid CA certificate "
            "(searched AIVEN_CA_PATH, /etc/secrets/aiven_ca.pem, and local aiven_ca.pem). "
            "Refusing to connect without certificate and identity verification."
        )
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