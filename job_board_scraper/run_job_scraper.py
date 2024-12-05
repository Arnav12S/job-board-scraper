import sys
import scrapy
import os
import logging
import psycopg2
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
from job_board_scraper.utils.postgres_wrapper import PostgresWrapper
from job_board_scraper.utils import general as util
from job_board_scraper.utils.scraper_util import get_url_chunks
from scrapy.utils.project import get_project_settings
import asyncio
from job_board_scraper.get_ashby_jobs import main_with_hash as run_ashby_scraper
from job_board_scraper.get_workable_jobs import main as run_workable_scraper
from job_board_scraper.get_recruitee_jobs import main as run_recruitee_scraper
from job_board_scraper.get_teamtailor_jobs import main as run_teamtailor_scraper
from job_board_scraper.get_smartrecruiters_jobs import main as run_smartrecruiters_scraper
from job_board_scraper.get_jobvite_jobs import main as run_jobvite_scraper
from job_board_scraper.get_rippling_jobs import main as run_rippling_scraper

logger = logging.getLogger("logger")
run_hash = util.hash_ids.encode(int(time.time()))


def run_spider(single_url_chunk, chunk_number):
    try:
        process = CrawlerProcess(get_project_settings())
        for i, careers_page_url in enumerate(single_url_chunk):
            logger.info(f"url = {careers_page_url}")
            url_id = chunk_number * len(single_url_chunk) + i
            
            # Extract domain from URL
            domain = careers_page_url.split(".")[1]
            
            if domain == "greenhouse":
                process.crawl(
                    GreenhouseJobDepartmentsSpider,
                    careers_page_url=careers_page_url,
                    use_existing_html=False,
                    run_hash=run_hash,
                    url_id=url_id,
                )
                process.crawl(
                    GreenhouseJobsOutlineSpider,
                    careers_page_url=careers_page_url,
                    use_existing_html=False,
                    run_hash=run_hash,
                    url_id=url_id,
                )
            elif domain == "lever":
                process.crawl(
                    LeverJobsOutlineSpider,
                    careers_page_url=careers_page_url,
                    use_existing_html=False,
                    run_hash=run_hash,
                    url_id=url_id,
                )
            elif domain == "ashby":
                run_ashby_scraper(careers_page_url, run_hash, url_id)
            elif domain == "recruitee":
                run_recruitee_scraper(careers_page_url, run_hash, url_id)
            elif domain == "teamtailor":
                asyncio.run(run_teamtailor_scraper(careers_page_url, run_hash, url_id))
            elif domain == "smartrecruiters":
                run_smartrecruiters_scraper(careers_page_url, run_hash, url_id)
            elif domain == "jobvite":
                run_jobvite_scraper(careers_page_url, run_hash, url_id)
            elif domain == "rippling":
                run_rippling_scraper(careers_page_url, run_hash, url_id)
            
# Only start the process if there are crawlers added
        process.start()
    except Exception as e:
        logger.error(f"Error running spider for chunk {chunk_number}: {e}")


if __name__ == "__main__":
    chunk_size = int(os.getenv("CHUNK_SIZE", 200))

    connection = psycopg2.connect(
        host=os.getenv("PG_HOST"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        dbname=os.getenv("PG_DATABASE"),
    )
    cursor = connection.cursor()
    cursor.execute(os.getenv("PAGES_TO_SCRAPE_QUERY"))
    careers_page_urls = cursor.fetchall()
    cursor.close()
    connection.close()
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
