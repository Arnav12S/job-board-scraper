import json
import polars as pl
import logging
import time
import os
from msgspec.json import decode
from msgspec import Struct
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass
import aiohttp
import asyncio
from supabase import create_client

from job_board_scraper.utils import general as util

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

# Database setup
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
if not supabase_url or not supabase_key:
    raise EnvironmentError("SUPABASE_URL and SUPABASE_KEY must be set")

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
    def __init__(self, supabase_client, batch_size: int = 100):
        self.supabase = supabase_client
        self.batch_size = batch_size
        self._jobs_batch = []
        self._departments_batch = []
        self._locations_batch = []

    def add_records(self, jobs: List[Dict], departments: List[Dict], locations: List[Dict]):
        self._jobs_batch.extend(jobs)
        self._departments_batch.extend(departments)
        self._locations_batch.extend(locations)
        
        if len(self._jobs_batch) >= self.batch_size:
            self.flush()

    async def flush(self):
        if not any([self._jobs_batch, self._departments_batch, self._locations_batch]):
            return

        try:
            if self._jobs_batch:
                await self.supabase.table("ashby_jobs_outline").upsert(self._jobs_batch).execute()
                logger.info(f"Successfully inserted {len(self._jobs_batch)} jobs")
                
            if self._departments_batch:
                await self.supabase.table("ashby_job_departments").upsert(self._departments_batch).execute()
                logger.info(f"Successfully inserted {len(self._departments_batch)} departments")
                
            if self._locations_batch:
                await self.supabase.table("ashby_job_locations").upsert(self._locations_batch).execute()
                logger.info(f"Successfully inserted {len(self._locations_batch)} locations")

            # Clear batches after successful write
            self._jobs_batch = []
            self._departments_batch = []
            self._locations_batch = []
            
        except Exception as e:
            logger.error(f"Failed to flush batches to database: {e}")
            raise

def process_company_data(
    company_name: str,
    response_data: Dict,
    run_hash: str,
    url_index: int
) -> tuple[List[Dict], List[Dict], List[Dict]]:
    """Process company data and return jobs, departments, and locations"""
    
    jobs = []
    departments = []
    locations = []
    
    try:
        posting_data = decode(
            json.dumps(response_data["data"]["jobBoard"]["jobPostings"]),
            type=list[Posting]
        )
        
        # Process postings and locations
        for j, record in enumerate(posting_data):
            # Process secondary locations
            if record.secondaryLocations:
                for k, location in enumerate(record.secondaryLocations):
                    locations.append({
                        "levergreen_id": determine_row_id(5, url_index, j, int(time.time()), k),
                        "opening_id": record.id,
                        "secondary_location_id": location.locationId,
                        "secondary_location_name": location.locationName,
                        "company_name": company_name,
                        "run_hash": run_hash
                    })
            
            # Process job posting
            jobs.append({
                "levergreen_id": determine_row_id(4, url_index, j, int(time.time())),
                "opening_id": record.id,
                "opening_name": record.title,
                "department_id": record.teamId,
                "location_id": record.locationId,
                "location_name": record.locationName,
                "employment_type": record.employmentType,
                "compensation_tier": record.compensationTierSummary,
                "company_name": company_name,
                "run_hash": run_hash,
                "ashby_job_board_source": f"https://jobs.ashbyhq.com/{company_name}",
                "raw_json_file_location": None,
                "existing_json_used": False,
                "opening_link": f"https://jobs.ashbyhq.com/{company_name}/{record.id}"
            })
        
        # Process departments
        team_data = decode(
            json.dumps(response_data["data"]["jobBoard"]["teams"]),
            type=list[Team]
        )
        
        for j, record in enumerate(team_data):
            departments.append({
                "levergreen_id": determine_row_id(3, url_index, j, int(time.time())),
                "department_id": record.id,
                "department_name": record.name,
                "parent_department_id": record.parentTeamId,
                "company_name": company_name,
                "run_hash": run_hash
            })
            
    except Exception as e:
        logger.error(f"Error processing data for {company_name}: {e}")
        
    return jobs, departments, locations

def determine_row_id(spider_id: int, url_id: int, row_id: int, created_at: int, k: int = 0) -> str:
    return util.hash_ids.encode(spider_id, url_id, row_id, created_at, k)

async def fetch_ashby_urls(connection_string: str) -> List[tuple]:
    query = """
        SELECT company_url FROM job_board_urls 
        WHERE ats = 'ashbyhq' AND is_enabled = true
    """
    df = pl.read_database(query, connection_string)
    return df.rows()

async def fetch_company_data(
    session: aiohttp.ClientSession,
    company_name: str,
    query: str,
    batch_processor: BatchProcessor,
    run_hash: str,
    url_index: int
):
    try:
        async with session.post(
            ASHBY_API_ENDPOINT,
            headers={"Content-Type": "application/json"},
            json={
                "query": query,
                "variables": {"organizationHostedJobsPageName": company_name}
            }
        ) as response:
            response_data = await response.json()
            
            if not response_data.get("data", {}).get("jobBoard"):
                logger.error(f"No data for {company_name}")
                return
                
            jobs, departments, locations = process_company_data(
                company_name,
                response_data,
                run_hash,
                url_index
            )
            
            batch_processor.add_records(jobs, departments, locations)
            
    except Exception as e:
        logger.error(f"Failed to process {company_name}: {e}")

async def main(careers_page_url: str, run_hash: str, url_id: int):
    try:
        # Create Supabase client
        supabase = create_client(supabase_url, supabase_key)
        
        # Initialize the batch processor with Supabase client
        batch_processor = BatchProcessor(supabase)

        # Read the GraphQL query from a file
        with open(QUERY_PATH, 'r') as f:
            query = f.read()

        # Extract the company name from the URL
        company_name = careers_page_url.split("/")[-1].replace("%20", " ")

        async with aiohttp.ClientSession() as session:
            # Fetch and process company data
            await fetch_company_data(
                session,
                company_name,
                query,
                batch_processor,
                run_hash,
                url_id
            )

        # Flush any remaining records
        batch_processor.flush()

    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main(None, None, None))  # Default values for direct script execution