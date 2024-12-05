import os
import psycopg2
from psycopg2 import pool
import logging

logger = logging.getLogger("postgres_wrapper")

class PostgresWrapper:
    _connection_pool = None

    @classmethod
    def initialize_pool(cls, minconn=1, maxconn=20):
        if cls._connection_pool is None:
            try:
                cls._connection_pool = pool.ThreadedConnectionPool(
                    minconn,
                    maxconn,
                    host=os.environ.get("PG_HOST"),
                    user=os.environ.get("PG_USER"),
                    password=os.environ.get("PG_PASSWORD"),
                    dbname=os.environ.get("PG_DATABASE"),
                    port=os.environ.get("PG_PORT", "5432")
                )
                logger.info("PostgreSQL connection pool created successfully")
            except Exception as e:
                logger.error(f"Error creating connection pool: {e}")
                raise

    @classmethod
    def get_connection(cls):
        if cls._connection_pool is None:
            cls.initialize_pool()
        try:
            conn = cls._connection_pool.getconn()
            if conn:
                logger.debug("Successfully retrieved connection from pool")
                return conn
        except Exception as e:
            logger.error(f"Error getting connection from pool: {e}")
            raise

    @classmethod
    def release_connection(cls, conn):
        try:
            cls._connection_pool.putconn(conn)
            logger.debug("Connection returned to pool")
        except Exception as e:
            logger.error(f"Error returning connection to pool: {e}")
            raise

    @classmethod
    def close_all_connections(cls):
        try:
            cls._connection_pool.closeall()
            logger.info("PostgreSQL connection pool closed")
        except Exception as e:
            logger.error(f"Error closing connection pool: {e}")
            raise

    @classmethod
    def get_cursor(cls):
        conn = cls.get_connection()
        try:
            cursor = conn.cursor()
            return cursor, conn
        except Exception as e:
            logger.error(f"Error creating cursor: {e}")
            cls.release_connection(conn)
            raise