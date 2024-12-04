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

    result = supabase.rpc(
        os.getenv("GET_BOARD_TOKENS_BASE_QUERY"),
        {'provider': job_board_provider}
    ).execute()

    board_tokens = [row['token'] for row in result.data]
    return board_tokens


def create_dataframes_factory(
    job_board_provider, jobs_outline_json, board_token, run_hash, source
):
    if job_board_provider == "rippling":
        return create_rippling_dataframes(
            jobs_outline_json, board_token, run_hash, source
        )


def job_board_api_factory(board_token, job_board):
    if job_board == "rippling":
        return call_rippling_job_board_api(board_token)


def initial_error_check(board_token, job_board):
    try:
        jobs_outline_json, source = job_board_api_factory(board_token, job_board)
    except (KeyError, TypeError, JSONDecodeError, HTTPError):
        logger.error(f"Bad Input for {board_token}")
        return True

    # No Jobs found
    if len(jobs_outline_json) == 0:
        logger.warning(f"No Jobs found for {board_token}")
        return True

    return False


def create_insert_item(table_name, item):
    columns = ', '.join(item.keys())
    placeholders = ', '.join(['%s'] * len(item))
    insert_statement = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
    values = [item[key] for key in item.keys()]
    return insert_statement, values
