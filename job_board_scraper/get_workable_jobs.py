import asyncio
import aiohttp
from supabase import create_client, Client
import os
from fast_langdetect import detect_language
import logging
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize Supabase client
url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

CHUNK_SIZE = 100  # Number of records to insert per chunk

# Retry configuration: Retry on 429 errors, wait exponentially, stop after 5 attempts
@retry(
    retry=retry_if_exception_type(aiohttp.ClientResponseError),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    stop=stop_after_attempt(5),
    reraise=True
)
async def fetch_with_retry(session, url, params):
    async with session.get(url, params=params) as response:
        if response.status == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                wait_time = int(retry_after)
            else:
                wait_time = 5  # Default wait time
            logging.warning(f"Rate limited. Retrying after {wait_time} seconds...")
            await asyncio.sleep(wait_time)
            raise aiohttp.ClientResponseError(
                status=response.status,
                message="Rate limited",
                request_info=response.request_info,
                history=response.history
            )
        elif response.status != 200:
            logging.error(f"Failed to fetch jobs: {response.status} - {await response.text()}")
            response.raise_for_status()
        return await response.json()

async def fetch_jobs():
    base_url = "https://jobs.workable.com/api/v1/jobs"
    params = {"limit": 9999}
    jobs = []
    
    # Clean up headers by removing any potential None values
    headers = {
        "Accept": "*/*",
        "Sec-Fetch-Site": "same-origin",
        "Referer": "https://jobs.workable.com/search",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15"
    }

    # Filter out any None values from headers
    headers = {k: v for k, v in headers.items() if k is not None and v is not None}

    async with aiohttp.ClientSession(headers=headers) as session:
        logging.info("Fetching the first page of jobs...")
        try:
            data = await fetch_with_retry(session, base_url, params)
            logging.debug(f"API Response: {data}")
            # Process the data as before
            jobs.extend(data.get("jobs", []))
            # Fetch remaining pages...
        except aiohttp.ClientResponseError as e:
            logging.error(f"Failed to fetch jobs after retries: {e}")
            return jobs

    return jobs

async def fetch_page(session, url, params, page_number):
    logging.info(f"Starting fetch for page {page_number}...")
    async with session.get(url, params=params) as response:
        if response.status != 200:
            logging.error(f"Failed to fetch page {page_number}: {response.status} - {await response.text()}")
            return []
        data = await response.json()
        logging.debug(f"Page {page_number} Response: {data}")
        return data.get("jobs", [])

async def insert_jobs_to_supabase(jobs):
    job_data_list = []
    company_data_list = []

    total_jobs = len(jobs)
    logging.info(f"Preparing to insert {total_jobs} jobs into Supabase.")

    for idx, job in enumerate(jobs, start=1):
        # Detect language of the job description
        try:
            description = job.get("description", "")
            language_iso = detect_language(description) if description else "unknown"
        except Exception as e:
            logging.error(f"Language detection failed: {e}")
            language_iso = "unknown"

        # Prepare job data for insertion
        job_data = {
            "department": job.get("department"),
            "id": job.get("id"),
            "title": job.get("title"),
            "state": job.get("state"),
            "description": description,
            "employmentType": job.get("employmentType"),
            "url": job.get("url"),
            "language": language_iso,
            "locations": job.get("locations"),
            "created": job.get("created"),
            "updated": job.get("updated"),
            "company_id": job.get("company", {}).get("id"),
            "company_title": job.get("company", {}).get("title"),
            "isFeatured": job.get("isFeatured"),
            "workplace": job.get("workplace"),
            "benefitsSection": job.get("benefitsSection", ""),
            "requirementsSection": job.get("requirementsSection", ""),
        }
        job_data_list.append(job_data)

        # Prepare company data for insertion
        company = job.get("company", {})
        company_data = {
            "id": company.get("id"),
            "title": company.get("title"),
            "website": company.get("website"),
            "image": company.get("image"),
            "description": company.get("description"),
            "url": company.get("url"),
            "socialSharingImage": company.get("socialSharingImage"),
            "socialSharingDescription": company.get("socialSharingDescription"),
        }
        company_data_list.append(company_data)

        # Insert in chunks
        if idx % CHUNK_SIZE == 0 or idx == total_jobs:
            logging.info(f"Inserting records {max(idx - CHUNK_SIZE + 1,1)} to {idx} into Supabase...")
            try:
                await supabase.table("workable_jobs_outline").upsert(job_data_list).execute()
                await supabase.table("workable_company_details").upsert(company_data_list).execute()
                logging.info(f"Inserted up to record {idx}.")
            except Exception as e:
                logging.error(f"Error inserting records up to {idx}: {e}")
            finally:
                job_data_list.clear()
                company_data_list.clear()

    logging.info("All records have been inserted into Supabase.")

async def main():
    jobs = await fetch_jobs()
    if jobs:
        await insert_jobs_to_supabase(jobs)
    else:
        logging.info("No jobs to insert.")

if __name__ == "__main__":
    asyncio.run(main())
