import asyncio
import aiohttp
from bs4 import BeautifulSoup
import logging
import time
import os
from supabase import create_client
from job_board_scraper.utils import general as util
from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def process_job(session, i, j, job, company_name, url, run_hash, current_time):
    try:
        # Generate levergreen_id
        levergreen_id = util.hash_ids.encode(i, j, current_time)

        job_data = {
            'levergreen_id': str(levergreen_id),
            #'created_at': current_time,
            #'updated_at': current_time,
            'source': url,
            'company_name': company_name,
            'opening_title': job.select_one('.jv-job-list-name').text.strip(),
            'opening_link': job.select_one('a')['href'],
            'location': job.select_one('.jv-job-list-location').text.strip() if job.select_one('.jv-job-list-location') else '',
            'run_hash': run_hash,
            'raw_html_file_location': None,
            'existing_html_used': False
        }
        
        logger.info(f"Extracted job: {job_data['opening_title']} from {company_name}")
        return job_data
    except Exception as e:
        logger.error(f"Error processing job {j} from {company_name}: {str(e)}")
        return None

async def process_company(session, i, url, supabase, run_hash, current_time, headers):
    company_name = url.split('//')[-1].split('.')[0]
    
    try:
        async with session.get(url, headers=headers) as response:
            content = await response.text()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Find all job listings
            job_listings = soup.select('ul.jv-job-list li')
            logger.info(f"Found {len(job_listings)} job listings for {company_name}")

            # Process jobs concurrently
            tasks = [
                process_job(session, i, j, job, company_name, url, run_hash, current_time)
                for j, job in enumerate(job_listings)
            ]
            all_jobs = await asyncio.gather(*tasks)
            all_jobs = [job for job in all_jobs if job is not None]

            # Batch insert/update jobs
            if all_jobs:
                for job_data in all_jobs:
                    try:
                        # Check if job exists
                        existing_job = supabase.table("jobvite_jobs_outline") \
                            .select("id") \
                            .eq("opening_link", job_data['opening_link']) \
                            .execute()
                        
                        if existing_job.data:
                            # Update existing job
                            job_id = existing_job.data[0]['id']
                            supabase.table("jobvite_jobs_outline") \
                                .update(job_data) \
                                .eq("id", job_id) \
                                .execute()
                            logger.info(f"Updated job: {job_data['opening_title']} for {company_name}")
                        else:
                            # Insert new job
                            supabase.table("jobvite_jobs_outline") \
                                .insert(job_data) \
                                .execute()
                            logger.info(f"Inserted new job: {job_data['opening_title']} for {company_name}")
                    except Exception as e:
                        logger.error(f"Error inserting/updating job '{job_data['opening_title']}' for {company_name}: {str(e)}")

    except Exception as e:
        logger.error(f"Error processing {company_name}: {str(e)}")

def fetch_all_jobvite_urls(supabase):
    all_urls = []
    offset = 0
    limit = 1000  # Fetch 1000 records at a time

    while True:
        response = supabase.table('job_board_urls') \
            .select('company_url') \
            .eq('ats', 'jobvite') \
            .eq('is_enabled', True) \
            .range(offset, offset + limit - 1) \
            .execute()

        if not response.data:
            break

        all_urls.extend([row['company_url'] for row in response.data])
        offset += limit

    return all_urls

async def main_with_params(careers_page_urls: List[str], run_hash: str):
    try:
        supabase = create_client(
            os.environ.get("SUPABASE_URL"),
            os.environ.get("SUPABASE_KEY")
        )
        
        current_time = int(time.time())
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        async with aiohttp.ClientSession() as session:
            tasks = [
                process_company(session, i, url, supabase, run_hash, current_time, headers)
                for i, url in enumerate(careers_page_urls)
            ]
            await asyncio.gather(*tasks)

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

def main_with_hash(careers_page_url: str, run_hash: str, url_id: int):
    try:
        asyncio.run(main_with_params([careers_page_url], run_hash))
    except Exception as e:
        logger.error(f"An unexpected error occurred processing {careers_page_url}: {e}")

if __name__ == "__main__":
    try:
        supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )
        careers_page_urls = fetch_all_jobvite_urls(supabase)
        # Generate run_hash only when running standalone
        run_hash = util.hash_ids.encode(int(time.time()))
        asyncio.run(main_with_params(careers_page_urls, run_hash))
    except Exception as e:
        logger.error(f"Script failed: {e}")