import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import Optional, Dict, Any

import aiohttp
import duckdb
import polars as pl
import requests
from msgspec import Struct
from msgspec.json import decode
from polars import DataFrame
from supabase import Client, create_client
from supabase import StorageException
from typing import List, Optional, Dict, Any

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
headers = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# Add near the top of the file, after the constants
def load_query():
    with open(QUERY_PATH, 'r') as f:
        return f.read()

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

class BatchProcessor:
    def __init__(self, supabase_client, batch_size=100):
        self.supabase = supabase_client
        self.batch_size = batch_size
        self.logger = logging.getLogger(__name__)
        self.validator = JobDataValidator()
        self._jobs_batch = []
        self._invalid_jobs = []

    async def add_job(self, job_data: Dict[str, Any]):
        validation_result = self.validator.validate_job_data(job_data)
        
        if validation_result.is_valid:
            self._jobs_batch.append(job_data)
            
            if len(self._jobs_batch) >= self.batch_size:
                await self.flush()
        else:
            self._invalid_jobs.append((job_data, validation_result.errors))
            self.logger.error(
                f"Invalid job data skipped",
                extra={
                    'job_data': job_data,
                    'validation_errors': validation_result.errors
                }
            )

    async def flush(self):
        if not self._jobs_batch:
            return

        try:
            self.logger.info(f"Processing batch of {len(self._jobs_batch)} jobs")
            
            response = await self.supabase.table("ashby_jobs_outline") \
                .upsert(self._jobs_batch, on_conflict="opening_link") \
                .execute()

            self.logger.info(
                f"Successfully processed batch",
                extra={'batch_size': len(self._jobs_batch)}
            )
            
            self._jobs_batch = []
            
        except Exception as e:
            self.logger.error(
                "Batch processing failed",
                extra={
                    'error': str(e),
                    'batch_size': len(self._jobs_batch)
                }
            )
            raise

    def get_invalid_jobs(self):
        return self._invalid_jobs

@dataclass
class JobValidationResult:
    is_valid: bool
    errors: Dict[str, str]

class JobDataValidator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def validate_job_data(self, job_data: Dict[str, Any]) -> JobValidationResult:
        errors = {}
        
        # Required fields validation
        required_fields = ['opening_title', 'opening_link', 'company_name', 'source']
        for field in required_fields:
            if not job_data.get(field):
                errors[field] = f"Missing required field: {field}"

        # URL format validation
        if job_data.get('opening_link'):
            if not job_data['opening_link'].startswith(('http://', 'https://')):
                errors['opening_link'] = "Invalid URL format"

        # Length validations
        if len(job_data.get('opening_title', '')) > 255:
            errors['opening_title'] = "Title exceeds maximum length of 255 characters"

        # Log validation results
        if errors:
            self.logger.warning(
                f"Validation failed for job: {job_data.get('opening_title', 'Unknown Title')}",
                extra={'errors': errors, 'job_data': job_data}
            )
        
        return JobValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )


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

async def process_company(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    url: str,
    supabase: Client,
    run_hash: str,
    batch_processor: BatchProcessor
):
    async with semaphore:
        try:
            company_name = url.split("/")[-1].replace("%20", " ")
            
            logger.info(f"Processing company: {company_name}", extra={
                'company': company_name,
                'url': url,
                'run_hash': run_hash
            })

            variables = {"organizationHostedJobsPageName": company_name}
            query = load_query()
            data = await fetch_ashby_data(session, ASHBY_API_ENDPOINT, query, headers, variables)

            if not data.get("data", {}).get("jobBoard"):
                logger.warning(f"No job board data for {company_name}", extra={
                    'company': company_name,
                    'url': url
                })
                return

            job_listings = data["data"]["jobBoard"]["jobPostings"]
            logger.info(f"Found {len(job_listings)} jobs for {company_name}")

            # Process jobs
            for job in job_listings:
                job_data = {
                    'levergreen_id': determine_row_id(4, 0, len(job_listings), int(time.time())),
                    'opening_title': job.get('title'),
                    'opening_link': f"https://jobs.ashbyhq.com/{company_name}/{job.get('id')}",
                    'company_name': company_name,
                    'source': url,
                    'run_hash': run_hash
                    # Add other fields as needed
                }
                
                await batch_processor.add_job(job_data)

            # Flush any remaining jobs in the batch
            await batch_processor.flush()

        except Exception as e:
            logger.error(f"Error processing {company_name}", extra={
                'company': company_name,
                'error': str(e),
                'url': url
            })
            raise

async def main_with_params(careers_page_urls: List[str], run_hash: str):
    try:
        supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        batch_processor = BatchProcessor(supabase)
        
        semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
        
        async with aiohttp.ClientSession() as session:
            tasks = [
                process_company(
                    session=session,
                    semaphore=semaphore,
                    url=url,
                    supabase=supabase,
                    run_hash=run_hash,
                    batch_processor=batch_processor
                )
                for url in careers_page_urls
            ]
            await asyncio.gather(*tasks)

        # Log statistics about invalid jobs
        invalid_jobs = batch_processor.get_invalid_jobs()
        if invalid_jobs:
            logger.warning(
                f"Found {len(invalid_jobs)} invalid jobs during processing",
                extra={'invalid_jobs_count': len(invalid_jobs)}
            )

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise

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