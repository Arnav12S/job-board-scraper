import os
import psycopg2
from psycopg2 import pool
import logging

logger = logging.getLogger("postgres_wrapper")

class PostgresWrapper:
    _connection_pool = None
    _pid = None

    @classmethod
    def initialize_pool(cls, minconn=1, maxconn=20):
        current_pid = os.getpid()
        
        if cls._connection_pool is None or cls._pid != current_pid:
            try:
                if cls._connection_pool is not None:
                    cls._connection_pool.closeall()
                    
                cls._connection_pool = pool.ThreadedConnectionPool(
                    minconn,
                    maxconn,
                    host=os.environ.get("PG_HOST"),
                    user=os.environ.get("PG_USER"),
                    password=os.environ.get("PG_PASSWORD"),
                    dbname=os.environ.get("PG_DATABASE"),
                    port=os.environ.get("PG_PORT", "6543")
                )
                cls._pid = current_pid
                logger.info(f"PostgreSQL connection pool created successfully for process {current_pid}")
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
        """Safely release a connection back to the pool"""
        try:
            if conn and cls._connection_pool:
                cls._connection_pool.putconn(conn)
                logger.debug("Released connection back to pool")
        except Exception as e:
            logger.error(f"Error releasing connection: {e}")
            # If we can't return it to pool, try to close it
            try:
                conn.close()
            except:
                pass

    @classmethod
    def close_all_connections(cls):
        try:
            if cls._connection_pool:
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