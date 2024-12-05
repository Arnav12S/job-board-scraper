import sys
import scrapy
import os
import logging
import psycopg2
import time
import multiprocessing
from scrapy.crawler import CrawlerProcess
from scrapy.settings import Settings
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
from get_ashby_jobs import main as run_ashby_scraper
from get_workable_jobs import main as run_workable_scraper
from get_recruitee_jobs import main as run_recruitee_scraper
from get_teamtailor_jobs import main as run_teamtailor_scraper
from get_smartrecruiters_jobs import main as run_smartrecruiters_scraper
from get_jobvite_jobs import main_with_hash as run_jobvite_scraper

logger = logging.getLogger("logger")
run_hash = util.hash_ids.encode(int(time.time()))


def get_ats_query(ats_name: str) -> str:
    """Generate SQL query for a specific ATS"""
    return f"SELECT DISTINCT company_url FROM job_board_urls WHERE ats = '{ats_name}' AND is_enabled;"

# Define the order of ATS to process
ats_order = [
    'greenhouse',
    'lever',
    'ashbyhq',
    'recruitee',
    'teamtailor',
    'smartrecruiters',
    'jobvite',
    'workable',
    'rippling'
]

def get_careers_page_urls_for_ats(ats_name):
    try:
        cursor, conn = PostgresWrapper.get_cursor()
        query = get_ats_query(ats_name)
        cursor.execute(query)
        careers_page_urls = cursor.fetchall()
        return careers_page_urls
    except Exception as e:
        logger.error(f"Error fetching career page URLs for {ats_name}: {e}")
        raise
    finally:
        cursor.close()
        PostgresWrapper.release_connection(conn)


def run_spider(single_url_chunk, chunk_number):
    # Initialize connection pool once for this worker process
    PostgresWrapper.initialize_pool()
    
    try:
        # Create a single CrawlerProcess for this chunk
        process = CrawlerProcess(get_project_settings())
        
        for i, careers_page_url in enumerate(single_url_chunk):
            try:
                logger.info(f"Processing URL {careers_page_url}")
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
                # For non-Scrapy scrapers, run them directly
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
                elif domain == "workable":
                    run_workable_scraper(careers_page_url, run_hash, url_id)
                    
            except Exception as e:
                logger.error(f"Error processing URL {careers_page_url}: {str(e)}")
                continue
        
        # Start the process after adding all spiders for this chunk
        if process.crawlers:
            process.start()
            
    except Exception as e:
        logger.error(f"Error in chunk {chunk_number}: {str(e)}")
    finally:
        # Clean up connections
        try:
            PostgresWrapper.close_all_connections()
            logger.info(f"Closed database connections for chunk {chunk_number}")
        except Exception as e:
            logger.error(f"Error closing connections for chunk {chunk_number}: {str(e)}")


if __name__ == "__main__":
    chunk_size = int(os.getenv("CHUNK_SIZE", 200))
    
    try:
        for ats in ats_order:
            logger.info(f"Processing ATS: {ats}")
            careers_page_urls = get_careers_page_urls_for_ats(ats)
            url_chunks = get_url_chunks(careers_page_urls, chunk_size)

            processes = []
            for i, single_url_chunk in enumerate(url_chunks):
                time.sleep(60)  # sleep to avoid issues exporting to Postgres
                p = multiprocessing.Process(target=run_spider, args=(single_url_chunk, i))
                processes.append(p)
                p.start()

            # Wait for all processes to complete before moving to next ATS
            for p in processes:
                p.join()
            
            logger.info(f"Completed processing ATS: {ats}")
            
    except Exception as e:
        logger.error(f"Error in main process: {str(e)}")
