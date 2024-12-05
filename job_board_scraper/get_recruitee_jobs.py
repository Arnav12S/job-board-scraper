import aiohttp
import asyncio
from bs4 import BeautifulSoup
import json
import uuid
import os
import logging
import time
from supabase import create_client
from dotenv import load_dotenv
from job_board_scraper.utils import general as util

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fetch_url(session, url, headers):
    async with session.get(url, headers=headers) as response:
        return await response.text()

async def process_url(session, url_data, headers, supabase, run_hash, i):
    url = url_data.get('url')
    if not url:
        logger.error(f"Missing URL in data: {url_data}")
        return

    company_name = url.split('//')[-1].split('.')[0]

    try:
        html_content = await fetch_url(session, url, headers)
        soup = BeautifulSoup(html_content, 'html.parser')
        
        div_element = soup.find('div', {
            'data-rendered': True,
            'data-component': 'PublicApp',
            'data-props': True
        })

        if div_element:
            data = json.loads(div_element.get('data-props'))
            jobs = data.get('appConfig', {}).get('offers', [])
            departments = data.get('appConfig', {}).get('departments', [])
            logger.info(f"Found {len(jobs)} job listings for {company_name}")

            all_jobs = []
            current_time = int(time.time())

            for j, job in enumerate(jobs):
                try:
                    # Safely get translations, defaulting to English or first available language
                    translations = job.get('translations', {})
                    lang = 'en' if 'en' in translations else next(iter(translations))
                    job_translation = translations.get(lang, {})

                    # Safely get department
                    department = None
                    if job.get('departmentId'):
                        dept = next((dept for dept in departments 
                                if dept['id'] == job['departmentId']), None)
                        if dept and 'translations' in dept:
                            dept_translations = dept['translations']
                            dept_lang = 'en' if 'en' in dept_translations else next(iter(dept_translations))
                            department = dept_translations.get(dept_lang, {}).get('name')

                    # Generate levergreen_id using hash_ids
                    levergreen_id = util.hash_ids.encode(i, j, current_time)
                    if not isinstance(levergreen_id, str):
                        try:
                            levergreen_id = str(levergreen_id)
                        except ValueError:
                            logger.error(f"levergreen_id '{levergreen_id}' is not a string. Skipping job.")
                            continue

                    job_data = {
                        'id': str(uuid.uuid4()),
                        'levergreen_id': levergreen_id,
                        'source': url,
                        'company_name': company_name,
                        'opening_title': job_translation.get('title', ''),
                        'department_names': department,
                        'location': f"{job.get('city', '')}, {job_translation.get('state', '')}, {job_translation.get('country', '')}",
                        'workplace_type': 'Hybrid' if job.get('hybrid') else ('Remote' if job.get('remote') else 'On-site'),
                        'opening_link': f"{url}o/{job.get('slug', '')}",
                        'run_hash': run_hash,
                        'description_html': job_translation.get('descriptionHtml', ''),
                        'highlights_html': job_translation.get('highlightHtml', ''),
                        'requirements_html': job_translation.get('requirementsHtml', ''),
                        'raw_html_file_location': None,
                        'existing_html_used': False
                    }
                    all_jobs.append(job_data)
                except Exception as e:
                    logger.error(f"Error processing job {j} from {company_name}: {str(e)}")
                    continue

            if all_jobs:
                for job_data in all_jobs:
                    try:
                        existing_job = supabase.table("recruitee_jobs_outline").select("id").eq("opening_link", job_data['opening_link']).execute()
                        
                        if existing_job.data:
                            job_id = existing_job.data[0]['id']
                            supabase.table("recruitee_jobs_outline").update(job_data).eq("id", job_id).execute()
                        else:
                            supabase.table("recruitee_jobs_outline").insert(job_data).execute()
                    except Exception as e:
                        logger.error(f"Error inserting/updating job '{job_data['opening_title']}' for {company_name}: {str(e)}")
        else:
            logger.error(f"No job data found for {company_name}")

    except Exception as e:
        logger.error(f"Error processing {company_name}: {str(e)}")

async def run_spider():
    try:
        # Initialize Supabase client
        supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )
        
        # Test connection
        test_response = supabase.table("recruitee_jobs_outline").select("*", count='exact').execute()
        logger.info(f"Connected to Supabase - current row count: {test_response.count}")
        
        # Get careers page URLs using pagination
        careers_page_urls = get_recruitee_urls(supabase)
        logger.info(f"Fetched {len(careers_page_urls)} career page URLs from Supabase")

        run_hash = str(int(time.time()))
        
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br'
        }

        async with aiohttp.ClientSession() as session:
            tasks = [
                process_url(session, url_data, headers, supabase, run_hash, i)
                for i, url_data in enumerate(careers_page_urls)
            ]
            await asyncio.gather(*tasks)

        try:
            final_count = supabase.table("recruitee_jobs_outline").select("*", count='exact').execute()
            logger.info(f"Final row count in Supabase: {final_count.count}")
        except Exception as e:
            logger.error(f"Error fetching final row count: {str(e)}")

    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        raise

def main():
    try:
        logger.info("Starting Recruitee jobs script")
        asyncio.run(run_spider())
        logger.info("Recruitee jobs script completed successfully")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        exit(1)

def get_recruitee_urls(supabase_client) -> list[dict]:
    all_urls = []
    offset = 0
    limit = 1000

    while True:
        response = supabase_client.table('job_board_urls') \
            .select('company_url') \
            .eq('ats', 'recruitee') \
            .eq('is_enabled', True) \
            .range(offset, offset + limit - 1) \
            .execute()

        batch = response.data
        if not batch:
            break

        urls = [{'url': row['company_url']} for row in batch]
        all_urls.extend(urls)
        offset += limit

    return all_urls

if __name__ == "__main__":
    main()
