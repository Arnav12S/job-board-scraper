import sys
import scrapy
import os
from dotenv import load_dotenv
import logging
import time
import multiprocessing
from scrapy.crawler import CrawlerProcess
from scrapy.settings import Settings
from job_board_scraper import settings as my_settings
from job_board_scraper.spiders.greenhouse_jobs_outline_spider import (
    GreenhouseJobsOutlineSpider,
)
from job_board_scraper.spiders.greenhouse_job_departments_spider import (
    GreenhouseJobDepartmentsSpider,
)
from job_board_scraper.spiders.lever_jobs_outline_spider import LeverJobsOutlineSpider
from job_board_scraper.utils import general as util
from job_board_scraper.utils.scraper_util import get_url_chunks
from scrapy.utils.project import get_project_settings
from supabase import create_client, Client
import get_ashby_jobs
import get_jobvite_jobs
import get_teamtailor_jobs
import get_recruitee_jobs
import get_smartrecruiters_jobs
import get_workable_jobs
from typing import List

logger = logging.getLogger("logger")
run_hash = util.hash_ids.encode(int(time.time()))

load_dotenv()

def run_spider(single_url_chunk, chunk_number):
    try:
        # Create a settings object and set it to your project settings
        settings = Settings()
        settings.setmodule(my_settings)

        process = CrawlerProcess(settings)
        for i, careers_page_url in enumerate(single_url_chunk):
            logger.info(f"url = {careers_page_url}")
            if careers_page_url.split(".")[1] == "greenhouse":
                process.crawl(
                    GreenhouseJobDepartmentsSpider,
                    careers_page_url=careers_page_url,
                    use_existing_html=False,
                    run_hash=run_hash,
                    url_id=chunk_number * len(single_url_chunk) + i,
                )
                process.crawl(
                    GreenhouseJobsOutlineSpider,
                    careers_page_url=careers_page_url,
                    use_existing_html=False,
                    run_hash=run_hash,
                    url_id=chunk_number * len(single_url_chunk) + i,
                )
            elif careers_page_url.split(".")[1] == "lever":
                process.crawl(
                    LeverJobsOutlineSpider,
                    careers_page_url=careers_page_url,
                    use_existing_html=False,
                    run_hash=run_hash,
                    url_id=chunk_number * len(single_url_chunk) + i,
                )
            elif careers_page_url.split(".")[1] == "recruitee":
                get_recruitee_jobs(careers_page_url=careers_page_url, run_hash=run_hash, url_id=chunk_number * len(single_url_chunk) + i)

            elif careers_page_url.split(".")[1] == "teamtailor":
                get_teamtailor_jobs(careers_page_url=careers_page_url, run_hash=run_hash, url_id=chunk_number * len(single_url_chunk) + i)

            elif careers_page_url.split(".")[1] == "smartrecruiters":
                get_smartrecruiters_jobs(careers_page_url=careers_page_url, run_hash=run_hash, url_id=chunk_number * len(single_url_chunk) + i)

            elif careers_page_url.split(".")[1] == "workable":
                get_workable_jobs(careers_page_url=careers_page_url, run_hash=run_hash, url_id=chunk_number * len(single_url_chunk) + i)

            elif careers_page_url.split(".")[1] == "jobvite":
                get_jobvite_jobs(careers_page_url=careers_page_url, run_hash=run_hash, url_id=chunk_number * len(single_url_chunk) + i)
                            
            elif careers_page_url.split(".")[1] == "ashbyhq":
                # Assuming get_ashby_jobs is a function you want to call
                # You might need to import it at the top of your file
                get_ashby_jobs(careers_page_url=careers_page_url, run_hash=run_hash, url_id=chunk_number * len(single_url_chunk) + i)
        process.start()
    except Exception as e:
        logger.error(f"Error running spider for chunk {chunk_number}: {e}")

def fetch_all_careers_page_urls(supabase_client: Client) -> List[dict]:
    all_urls = []
    offset = 0
    limit = 1000

    while True:
        response = supabase_client.table('job_board_urls') \
            .select('company_url') \
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

def create_supabase_client():
    try:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
        if not url or not key:
            raise ValueError("SUPABASE_URL or SUPABASE_KEY environment variables are not set")
            
        client = create_client(url, key)
        # Test the connection using an existing table
        client.table("job_board_urls").select("*").limit(1).execute()
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {str(e)}")
        raise

if __name__ == "__main__":
    chunk_size = int(os.getenv("CHUNK_SIZE", 200))

    supabase = create_supabase_client()
    
    # Fetch careers page URLs using the new function
    careers_page_urls = fetch_all_careers_page_urls(supabase)
    url_chunks = get_url_chunks(careers_page_urls, chunk_size)

    num_processes = len(url_chunks)
    processes = []

    for i, single_url_chunk in enumerate(url_chunks):
        time.sleep(60)  # sleep to avoid issues exporting to Postgres
        p = multiprocessing.Process(target=run_spider, args=(single_url_chunk, i))
        processes.append(p)
        p.start()

    for p in processes:
        time.sleep(60)  # sleep to avoid issues exporting to Postgres
        p.join()
