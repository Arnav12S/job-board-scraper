from hashids import Hashids
import os
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("logger")

hash_ids = Hashids(
    salt=os.getenv("HASHIDS_SALT"), 
    alphabet="abcdefghijklmnopqrstuvwxyz1234567890"
)

def setup_supabase_connection(job_board_provider):
    supabase = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_KEY")
    )
    
    # Query using Supabase
    result = supabase.rpc(
        'get_board_tokens',
        {'provider': job_board_provider}
    ).execute()
    
    board_tokens = [row['token'] for row in result.data]
    return board_tokens
