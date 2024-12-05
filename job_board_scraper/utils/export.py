import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

def create_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        raise ValueError("SUPABASE_URL or SUPABASE_KEY environment variables are not set")
        
    return create_client(url, key)

def export_table_to_postgres(df, table_name):
    supabase = create_supabase_client()
    
    # Convert DataFrame to list of dictionaries
    records = df.to_dicts()
    
    try:
        # Use upsert to handle both inserts and updates
        response = supabase.table(table_name).upsert(records).execute()
        if hasattr(response, 'error') and response.error:
            raise Exception(f"Error upserting data: {response.error}")
    except Exception as e:
        raise Exception(f"Failed to export data to {table_name}: {str(e)}")

def determine_table_names(job_board_provider):
    if job_board_provider == "rippling":
        return [os.getenv("RIPPLING_JOBS_OUTLINE_TABLE_NAME")]

def export_dataframes_to_postgres(table_pairs_dict):
    for key, value in table_pairs_dict.items():
        if len(value) != 0:
            export_table_to_postgres(df=value, table_name=key)
