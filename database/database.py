import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from contextlib import contextmanager
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Get database connection details from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Fallback to manual connection string if DATABASE_URL is not set
    db_host = os.getenv("PGHOST", "localhost")
    db_port = os.getenv("PGPORT", "5432")
    db_name = os.getenv("PGDATABASE", "neondb")
    db_user = os.getenv("PGUSER", "neondb_owner")
    db_password = os.getenv("PGPASSWORD", "")
    
    DATABASE_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

# Create engine with connection pooling and pre-ping
engine = None

def get_engine():
    """Get the SQLAlchemy engine instance, creating it if necessary"""
    global engine
    if engine is None:
        try:
            logger.info("Creating database engine...")
            engine = create_engine(
                DATABASE_URL,
                pool_pre_ping=True,  # Enable connection health checks
                pool_recycle=300,    # Recycle connections every 5 minutes
                echo=False,          # Set to True for SQL query logging
            )
            logger.info("Database engine created successfully")
        except Exception as e:
            logger.error(f"Error creating database engine: {e}")
            raise
    return engine

# Create session factory
SessionFactory = None

def get_session_factory():
    """Get the session factory, creating it if necessary"""
    global SessionFactory
    if SessionFactory is None:
        engine = get_engine()
        SessionFactory = scoped_session(sessionmaker(bind=engine))
    return SessionFactory

@contextmanager
def get_session():
    """Context manager for database sessions"""
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Session error: {e}")
        raise
    finally:
        session.close()
