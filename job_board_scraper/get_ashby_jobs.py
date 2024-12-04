import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import aiohttp
import duckdb
import polars as pl
import requests
from msgspec import Struct
from msgspec.json import decode
from polars import DataFrame
from supabase import Client, create_client
from supabase import StorageException
from typing import List, Optional

from job_board_scraper.utils import general as util
import dotenv

# Load environment variables
dotenv.load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Constants
ASHBY_API_ENDPOINT = "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams"
QUERY_PATH = "queries/ashby_jobs_outline.graphql"
CONCURRENT_REQUESTS = 10  # Adjust based on your needs

# Database and Supabase setup
def get_postgres_connection_string(supabase_url: str, supabase_key: str) -> str:
    parsed = urlparse(supabase_url)
    return f"postgresql://postgres:{supabase_key}@{parsed.hostname}:5432/postgres"

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    logger.error("SUPABASE_URL and SUPABASE_KEY must be set in environment variables.")
    exit(1)

supabase: Client = create_client(supabase_url, supabase_key)

# Data Structures
class SecondaryLocation(Struct):
    locationId: str
    locationName: str

class Posting(Struct):
    id: str
    title: str
    teamId: str
    locationId: str
    locationName: str
    employmentType: str
    compensationTierSummary: Optional[str]
    secondaryLocations: Optional[List[SecondaryLocation]]

class Team(Struct):
    id: str
    name: str
    parentTeamId: Optional[str]

# Helper Functions
def determine_row_id(spider_id: int, url_id: int, row_id: int, created_at: int, k: int = 0) -> str:
    return util.hash_ids.encode(spider_id, url_id, row_id, created_at, k)

def set_initial_table_schema(table_name: str) -> str:
    return f"""CREATE TABLE IF NOT EXISTS {table_name} ( 
        id serial PRIMARY KEY,
        levergreen_id text,
        created_at bigint,
        updated_at bigint,
        company_name text,
        source text,
        run_hash text,
        raw_json_file_location text,
        existing_json_used boolean
    )"""

def create_table_schema(table_name: str, initial_table_schema: str = "") -> str:
    extensions = {
        "ashby_job_locations": """, opening_id uuid,
            secondary_location_id uuid,
            secondary_location_name text,
            CONSTRAINT unique_opening_secondary_location UNIQUE (opening_id, secondary_location_id)
        )""",
        "ashby_job_departments": """, department_id uuid,
            department_name text,
            parent_department_id uuid,
            CONSTRAINT unique_department_id UNIQUE (department_id)
        )""",
        "ashby_jobs_outline": """, opening_id uuid,
            opening_name text,
            department_id uuid,
            location_id uuid,
            location_name text,
            employment_type text,
            compensation_tier text,
            opening_link text UNIQUE,
            CONSTRAINT unique_opening_link UNIQUE (opening_link)
        )"""
    }
    return initial_table_schema + extensions.get(table_name, ")")

def finalize_table_schema(table_name: str) -> str:
    initial_schema = set_initial_table_schema(table_name)
    return create_table_schema(table_name, initial_schema)

def fetch_all_ashby_urls(supabase_client: Client) -> List[str]:
    all_urls = []
    offset = 0
    limit = 1000  # Fetch 1000 records at a time

    logger.info("Fetching Ashby URLs from Supabase.")
    while True:
        response = supabase_client.table('job_board_urls') \
            .select('company_url') \
            .eq('ats', 'ashbyhq') \
            .eq('is_enabled', True) \
            .range(offset, offset + limit - 1) \
            .execute()

        batch = response.data
        if not batch:
            break

        urls = [row['company_url'] for row in batch]
        all_urls.extend(urls)
        offset += limit
        logger.debug(f"Fetched {len(urls)} URLs. Total so far: {len(all_urls)}")

    logger.info(f"Total Ashby URLs fetched: {len(all_urls)}")
    return all_urls

async def fetch_ashby_data(session: aiohttp.ClientSession, url: str, query: str, headers: dict, variables: dict) -> dict:
    try:
        async with session.post(url, json={"query": query, "variables": variables}, headers=headers) as response:
            response.raise_for_status()
            data = await response.json()
            logger.debug(f"Successfully fetched data for URL: {url}")
            return data
    except aiohttp.ClientError as e:
        logger.error(f"HTTP error for URL {url}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error for URL {url}: {e}")
    return {}

async def process_company(session: aiohttp.ClientSession, semaphore: asyncio.Semaphore, url: str, query: str, headers: dict, ashby_api_endpoint: str, run_hash: str, con: duckdb.DuckDBPyConnection):
    async with semaphore:
        ashby_company = url.split("/")[-1].replace("%20", " ")

        variables = {"organizationHostedJobsPageName": ashby_company}
        data = await fetch_ashby_data(session, ashby_api_endpoint, query, headers, variables)

        if not data.get("data", {}).get("jobBoard"):
            logger.info(f"No job board data found for {ashby_company}. Skipping.")
            return

        job_listings = data["data"]["jobBoard"]["jobPostings"]
        logger.info(f"{ashby_company}: Found {len(job_listings)} jobs")

        ashby_postings_final = []
        ashby_departments_final = []
        ashby_locations_final = []

        try:
            # Process Postings
            posting_data = decode(json.dumps(job_listings), type=List[Posting])
            for j, record in enumerate(posting_data):
                # Process Secondary Locations
                all_locations_json = []
                if record.secondaryLocations:
                    for k, location in enumerate(record.secondaryLocations):
                        location_json_record = {
                            "levergreen_id": determine_row_id(5, j, k, 0, k),
                            "opening_id": record.id,
                            "secondary_location_id": location.locationId,
                            "secondary_location_name": location.locationName
                        }
                        all_locations_json.append(location_json_record)

                if all_locations_json:
                    df_locations = pl.DataFrame(all_locations_json)
                    df_locations = df_locations.with_columns([
                        pl.lit(ashby_company).alias("company_name"),
                        pl.lit(f"https://jobs.ashbyhq.com/{ashby_company}").alias("source"),
                        pl.lit(run_hash).alias("run_hash"),
                        pl.lit(False).alias("existing_json_used"),
                        pl.lit(None).alias("raw_json_file_location")
                    ])
                    ashby_locations_final.append(df_locations)

                # Process Postings
                posting_json_record = {
                    "levergreen_id": determine_row_id(4, j, j, 0),
                    "opening_id": record.id,
                    "opening_name": record.title,
                    "department_id": record.teamId,
                    "location_id": record.locationId,
                    "location_name": record.locationName,
                    "employment_type": record.employmentType,
                    "compensation_tier": record.compensationTierSummary,
                    "opening_link": f"https://jobs.ashbyhq.com/{ashby_company}/{record.id}",
                    "company_name": ashby_company,
                    "source": f"https://jobs.ashbyhq.com/{ashby_company}",
                    "run_hash": run_hash,
                    "existing_json_used": False,
                    "raw_json_file_location": None
                }

                ashby_postings_final.append(posting_json_record)

            if ashby_postings_final:
                # Convert postings to Polars DataFrame
                df_postings = pl.DataFrame(ashby_postings_final)

                # Convert DataFrame to list of dictionaries
                postings_dicts = df_postings.to_dicts()

                # Perform upsert
                try:
                    response = supabase.table("ashby_jobs_outline").upsert(postings_dicts, on_conflict="opening_link").execute()
                    if hasattr(response, 'error') and response.error:
                        logger.error(f"Upsert error: {response.error}")
                    else:
                        logger.debug(f"{ashby_company}: Upserted {len(postings_dicts)} job postings.")
                except StorageException as e:
                    logger.error(f"Supabase upsert error: {e}")

            # Insert Locations
            if ashby_locations_final:
                df_all_locations = pl.concat(ashby_locations_final)
                try:
                    # Corrected on_conflict parameter
                    response = supabase.table("ashby_job_locations").upsert(df_all_locations.to_dicts(), on_conflict="opening_id,secondary_location_id").execute()
                    if hasattr(response, 'error') and response.error:
                        logger.error(f"Upsert error for locations: {response.error}")
                    else:
                        logger.debug(f"{ashby_company}: Upserted {len(df_all_locations)} locations.")
                except StorageException as e:
                    logger.error(f"Supabase upsert error for locations: {e}")

            # Process Teams
            team_data = decode(json.dumps(data["data"]["jobBoard"]["teams"]), type=List[Team])
            all_teams_json = []
            for j, record in enumerate(team_data):
                team_json_record = {
                    "levergreen_id": determine_row_id(4, j, j, 0),
                    "department_id": record.id,
                    "department_name": record.name,
                    "parent_department_id": record.parentTeamId,
                    "company_name": ashby_company,
                    "source": f"https://jobs.ashbyhq.com/{ashby_company}",
                    "run_hash": run_hash,
                    "existing_json_used": False,
                    "raw_json_file_location": None
                }
                all_teams_json.append(team_json_record)

            # Insert Departments using Upsert
            if all_teams_json:
                df_departments = pl.DataFrame(all_teams_json)
                departments_dicts = df_departments.to_dicts()

                try:
                    response = supabase.table("ashby_job_departments").upsert(departments_dicts, on_conflict="department_id").execute()
                    if hasattr(response, 'error') and response.error:
                        logger.error(f"Upsert error for departments: {response.error}")
                    else:
                        logger.debug(f"{ashby_company}: Upserted {len(departments_dicts)} departments.")
                except StorageException as e:
                    logger.error(f"Supabase upsert error for departments: {e}")

        except Exception as e:
            logger.error(f"Error processing {ashby_company}: {str(e)}")

async def main_with_params(careers_page_urls: List[str], run_hash: str):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    query_path = os.path.join(current_dir, QUERY_PATH)

    # Read GraphQL query
    try:
        with open(query_path, 'r') as f:
            query = f.read()
        logger.info("Successfully read GraphQL query.")
    except FileNotFoundError:
        logger.error(f"GraphQL query file not found at {query_path}.")
        return
    except Exception as e:
        logger.error(f"Error reading GraphQL query: {e}")
        return

    headers = {"Content-Type": "application/json"}

    # Initialize DuckDB
    try:
        con = duckdb.connect(database=":memory:")
        logger.info("DuckDB connection established.")
    except Exception as e:
        logger.error(f"Failed to connect to DuckDB: {e}")
        return

    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async with aiohttp.ClientSession() as session:
        tasks = [
            process_company(
                session=session,
                semaphore=semaphore,
                url=url,
                query=query,
                headers=headers,
                ashby_api_endpoint=ASHBY_API_ENDPOINT,
                run_hash=run_hash,
                con=con
            )
            for url in careers_page_urls
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    # Close DuckDB connection
    con.close()
    logger.info("DuckDB connection closed.")

# New function to handle single URL processing (for run_job_scraper.py)
def main_with_hash(careers_page_url: str, run_hash: str, url_id: int):
    try:
        # Run async code for single URL
        asyncio.run(main_with_params([careers_page_url], run_hash))
    except Exception as e:
        logger.error(f"An unexpected error occurred processing {careers_page_url}: {e}")

# Modify the original entry point
if __name__ == "__main__":
    try:
        careers_page_urls = fetch_all_ashby_urls(supabase)
        logger.info(f"Found {len(careers_page_urls)} Ashby URLs to scrape.")
        # Generate run_hash only when running standalone
        run_hash = util.hash_ids.encode(int(time.time()))
        asyncio.run(main_with_params(careers_page_urls, run_hash))
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
