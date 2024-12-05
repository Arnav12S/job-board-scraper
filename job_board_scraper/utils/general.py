from hashids import Hashids
import os
from utils.rippling.parsing_helper import (
    call_rippling_job_board_api,
    create_rippling_dataframes,
)
from json import JSONDecodeError
from urllib.error import HTTPError
from dotenv import load_dotenv
from supabase import create_client
import logging

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("logger")

hash_ids = Hashids(
    salt=os.getenv("HASHIDS_SALT"), alphabet="abcdefghijklmnopqrstuvwxyz1234567890"
)


def setup_supabase_connection(job_board_provider):
    supabase = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_KEY")
    )

    result = supabase.table('job_board_urls') \
            .select('company_url') \
            .eq('ats', job_board_provider) \
            .eq('is_enabled', True) \
            .execute()

    company_url = [row['company_url'] for row in result.data]
    return company_url


def create_dataframes_factory(
    job_board_provider, jobs_outline_json, company_url, run_hash, source
):
    if job_board_provider == "rippling":
        return create_rippling_dataframes(
            jobs_outline_json, company_url, run_hash, source
        )


def job_board_api_factory(company_url, job_board):
    if job_board == "rippling":
        return call_rippling_job_board_api(company_url)


def initial_error_check(company_url, job_board):
    try:
        jobs_outline_json, source = job_board_api_factory(company_url, job_board)
    except (KeyError, TypeError, JSONDecodeError, HTTPError):
        logger.error(f"Bad Input for {company_url}")
        return True

    # No Jobs found
    if len(jobs_outline_json) == 0:
        logger.warning(f"No Jobs found for {company_url}")
        return True

    return False


def create_insert_item(table_name, item):
    columns = ', '.join(item.keys())
    placeholders = ', '.join(['%s'] * len(item))
    insert_statement = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
    values = [item[key] for key in item.keys()]
    return insert_statement, values
