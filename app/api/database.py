from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

postgres_username = "postgres"
postgres_password = "root123"
postgres_database = "z_ads_telegram_client"
database_url = f'postgresql://{postgres_username}:{postgres_password}@localhost:5432/{postgres_database}'

engine = create_engine(database_url)
SessionLocal = sessionmaker(autoflush=False, bind=engine)

Base = declarative_base()
