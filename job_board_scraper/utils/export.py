import os
from dotenv import load_dotenv
from job_board_scraper.utils.postgres_wrapper import PostgresWrapper
import logging

logger = logging.getLogger("export")

load_dotenv()

def export_table_to_postgres(df, table_name):
    try:
        cursor, conn = PostgresWrapper.get_cursor()
        df.write_database(
            table_name=table_name,
            connection=conn,
            if_exists="append",
            engine="sqlalchemy",
        )
        logger.info(f"Successfully exported data to {table_name}")
    except Exception as e:
        logger.error(f"Failed to export table {table_name}: {e}")
        raise
    finally:
        cursor.close()
        PostgresWrapper.release_connection(conn)

def determine_table_names(job_board_provider):
    if job_board_provider == "rippling":
        return [os.getenv("RIPPLING_JOBS_OUTLINE_TABLE_NAME")]

def export_dataframes_to_postgres(table_pairs_dict):
    for key, value in table_pairs_dict.items():
        if len(value) != 0:
            export_table_to_postgres(df=value, table_name=key)