import asyncio
import json
import logging
import os
import time
from typing import List, Optional
import aiohttp
from supabase import create_client, Client
from dotenv import load_dotenv
from job_board_scraper.utils import general as util
from http.cookies import SimpleCookie

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Constants
CONCURRENT_REQUESTS = 10

def fetch_all_smartrecruiters_urls(supabase_client: Client) -> List[str]:
    all_urls = []
    offset = 0
    limit = 1000

    logger.info("Fetching SmartRecruiters URLs from Supabase.")
    while True:
        response = supabase_client.table('job_board_urls') \
            .select('company_url') \
            .eq('ats', 'smartrecruiters') \
            .eq('is_enabled', True) \
            .range(offset, offset + limit - 1) \
            .limit(10) \
            .execute()

        batch = response.data
        if not batch:
            break

        urls = [row['company_url'] for row in batch]
        all_urls.extend(urls)
        offset += limit
        logger.debug(f"Fetched {len(urls)} URLs. Total so far: {len(all_urls)}")

    logger.info(f"Total SmartRecruiters URLs fetched: {len(all_urls)}")
    return all_urls

async def fetch_jobs_data(session: aiohttp.ClientSession, url: str, headers: dict, page: int) -> Optional[dict]:
    try:
        api_url = f"{url}/api/groups?page={page}"
        async with session.get(api_url, headers=headers) as response:
            if response.status == 404:
                logger.info(f"Received 404 for URL {api_url}. No more pages.")
                return None
            
            # Extract and update cookies from response
            if 'set-cookie' in response.headers:
                cookie = SimpleCookie()
                for cookie_str in response.headers.getall('set-cookie', []):
                    cookie.load(cookie_str)
                
                # Update session cookies with new values
                session.cookie_jar.update_cookies(cookie)
                
            response.raise_for_status()
            data = await response.json()
            return data
    except aiohttp.ClientError as e:
        logger.error(f"HTTP error for URL {url} on page {page}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error for URL {url} on page {page}: {e}")
    return {}

async def process_company(
    session: aiohttp.ClientSession, 
    semaphore: asyncio.Semaphore, 
    url: str, 
    supabase: Client,
    run_hash: str,
    headers: dict
):
    async with semaphore:
        company_name = url.split('/')[-1]
        
        try:
            all_jobs = []
            current_time = int(time.time())
            page = 1

            while True:
                logger.info(f"Processing {company_name} - Page {page}")
                data = await fetch_jobs_data(session, url, headers, page)
                
                if data is None:
                    # Received 404, stop pagination
                    break

                if not data.get('content'):
                    logger.info(f"No job data found for {company_name} on page {page}. Stopping pagination.")
                    break

                for section in data['content']:
                    location = section.get('title', '')
                    for job in section.get('jobs', []):
                        job_data = {
                            'levergreen_id': util.hash_ids.encode(5, 0, len(all_jobs), current_time),
                            'source': url,
                            'company_name': company_name,
                            'opening_title': job.get('title'),
                            'department_names': job.get('department', ''),
                            'location': location,
                            'workplace_type': job.get('type', 'Full-time'),
                            'opening_link': job.get('url'),
                            'run_hash': run_hash,
                            'raw_html_file_location': None,
                            'existing_html_used': False
                        }
                        all_jobs.append(job_data)

                logger.debug(f"Fetched {len(data['content'])} sections from page {page}.")
                page += 1

            if all_jobs:
                for job_data in all_jobs:
                    try:
                        existing_job = supabase.table("smartrecruiters_jobs_outline") \
                            .select("id") \
                            .eq("opening_link", job_data['opening_link']) \
                            .execute()
                        
                        if existing_job.data:
                            job_id = existing_job.data[0]['id']
                            supabase.table("smartrecruiters_jobs_outline") \
                                .update(job_data) \
                                .eq("id", job_id) \
                                .execute()
                            logger.debug(f"Updated job: {job_data['opening_title']}")
                        else:
                            supabase.table("smartrecruiters_jobs_outline") \
                                .insert(job_data) \
                                .execute()
                            logger.debug(f"Inserted new job: {job_data['opening_title']}")
                    except Exception as e:
                        logger.error(f"Error upserting job '{job_data['opening_title']}': {str(e)}")

        except Exception as e:
            logger.error(f"Error processing {company_name}: {str(e)}")

async def main():
    try:
        # Initialize Supabase client
        supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )
        
        # Test connection
        test_response = supabase.table("smartrecruiters_jobs_outline").select("*", count='exact').execute()
        logger.info(f"Connected to Supabase - current row count: {test_response.count}")

        # Get careers page URLs
        careers_page_urls = fetch_all_smartrecruiters_urls(supabase)
        logger.info(f"Found {len(careers_page_urls)} SmartRecruiters URLs to scrape")

        run_hash = str(int(time.time()))
        
        semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

        # Create cookie jar and session without headers
        cookie_jar = aiohttp.CookieJar(unsafe=True)
        async with aiohttp.ClientSession(cookie_jar=cookie_jar) as session:
            tasks = [
                process_company(
                    session=session,
                    semaphore=semaphore,
                    url=url,
                    supabase=supabase,
                    run_hash=run_hash,
                    headers={
                        'Pragma': 'no-cache',
                        'Accept': '*/*',
                        'Sec-Fetch-Site': 'same-origin',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Cache-Control': 'no-cache',
                        'Sec-Fetch-Mode': 'cors',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15',
                        'Referer': url,
                        'Connection': 'keep-alive',
                        'Sec-Fetch-Dest': 'empty',
                        'X-Requested-With': 'XMLHttpRequest',
                        'Priority': 'u=3, i'
                    }
                )
                for url in careers_page_urls
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

        # Log final count
        final_count = supabase.table("smartrecruiters_jobs_outline").select("*", count='exact').execute()
        logger.info(f"Final row count in Supabase: {final_count.count}")

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise

def run():
    try:
        logger.info("Starting SmartRecruiters jobs script")
        asyncio.run(main())
        logger.info("SmartRecruiters jobs script completed successfully")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        exit(1)

if __name__ == "__main__":
    run() 