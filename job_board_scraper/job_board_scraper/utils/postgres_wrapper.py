import os
import psycopg2
import sqlalchemy
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

class PostgresWrapper:
    def __init__(self):
        # Connection Details
        self.username = os.getenv("PG_USER")
        self.password = os.getenv("PG_PASSWORD")
        self.host = os.getenv("PG_HOST")
        self.database = os.getenv("PG_DATABASE")
        self.port = os.getenv("PG_PORT", "5432")
        
        if not all([self.username, self.password, self.host, self.database]):
            raise ValueError("Missing required database environment variables")
        
        # Create database URL
        self.db_url = URL.create(
            "postgresql+psycopg2",
            username=self.username,
            password=self.password,
            host=self.host,
            database=self.database,
            port=self.port
        )
        
        # Create engine
        self.engine = create_engine(self.db_url)
        
        # Create session factory
        self.Session = sessionmaker(bind=self.engine)

    @contextmanager
    def get_session(self):
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def execute_query(self, query, params=None):
        with self.engine.connect() as connection:
            if params:
                result = connection.execute(text(query), params)
            else:
                result = connection.execute(text(query))
            return result

    def upsert(self, table_name, data, unique_columns):
        """
        Perform an upsert operation using ON CONFLICT
        """
        if not data:
            return
        
        # Convert single dict to list
        if isinstance(data, dict):
            data = [data]
            
        # Get column names from first record
        columns = list(data[0].keys())
        
        # Build the ON CONFLICT clause
        conflict_columns = ",".join(unique_columns)
        update_set = ",".join([f"{col} = EXCLUDED.{col}" for col in columns if col not in unique_columns])
        
        # Build the insert statement
        placeholders = ",".join([f":{col}" for col in columns])
        query = f"""
            INSERT INTO {table_name} ({",".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT ({conflict_columns})
            DO UPDATE SET {update_set}
        """
        
        with self.get_session() as session:
            for record in data:
                session.execute(text(query), record)
