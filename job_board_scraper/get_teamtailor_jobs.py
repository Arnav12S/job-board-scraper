import asyncio
import aiohttp
import logging
import os
import time
from scrapy.selector import Selector
from supabase import create_client, Client
from dotenv import load_dotenv
from job_board_scraper.utils import general as util
from typing import List, Optional

load_dotenv()

logger = logging.getLogger(__name__)

async def fetch_page(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    try:
        async with session.get(url, allow_redirects=True) as response:
            if response.status == 200:
                return await response.text()
            elif response.status != 404:
                logger.warning(f"Unexpected status {response.status} for {url}")
            return None
    except aiohttp.ClientError as e:
        logger.error(f"Failed to fetch {url}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching {url}: {str(e)}")
        return None

async def process_company(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    url: str,
    company_name: str,
    run_hash: str,
    supabase: Client,
    index: int,
    total_urls: int
):
    async with semaphore:
        try:
            current_page = 1
            total_jobs = 0
            
            base_url = url.rstrip('/')
            if '/jobs' in base_url:
                base_url = base_url[:base_url.index('/jobs')]
            
            logger.info(f"🔄 [{index + 1}/{total_urls}] Starting scrape for {company_name} at {base_url}")
            
            while True:
                page_url = f"{base_url}/jobs?page={current_page}"
                logger.debug(f"{company_name}: Fetching page {current_page} from {page_url}")
                
                html = await fetch_page(session, page_url)
                
                if not html:
                    if current_page == 1:
                        logger.warning(f"{company_name}: No jobs found at {url}")
                    break

                selector = Selector(text=html)
                job_listings = selector.xpath('//ul[@id="jobs_list_container"]/li')
                
                if not job_listings:
                    logger.info(f"{company_name}: No more jobs found, ending at page {current_page}")
                    break

                all_jobs = []
                for job in job_listings:
                    try:
                        job_link = job.xpath('.//a[@class="flex flex-col py-6 text-center sm:px-6 hover:bg-gradient-block-base-bg focus-visible-company focus-visible:rounded"]/@href').get()
                        if not job_link:
                            continue
                            
                        job_title = job.xpath('.//span[@class="text-block-base-link sm:min-w-[25%] sm:truncate company-link-style"]/@title').get()
                        info_spans = job.xpath('.//div[@class="mt-1 text-md"]/span[not(contains(@class, "mx-[2px]"))]/text()').getall()
                        info_spans = [span.strip() for span in info_spans if span.strip()]

                        department = info_spans[0] if info_spans else None
                        location = info_spans[1] if len(info_spans) > 1 else None

                        workplace_type = None
                        workplace_span = job.xpath('.//span[contains(@class, "inline-flex")]/text()').get()
                        if workplace_span:
                            workplace_type = workplace_span.strip()

                        job_data = {
                            "opening_title": job_title,
                            "opening_link": job_link,
                            "location": location,
                            "workplace_type": workplace_type,
                            "department_names": department,
                            "source": url,
                            "company_name": company_name,
                            "run_hash": run_hash,
                            "raw_html_file_location": None,
                            "existing_html_used": False
                        }
                        
                        all_jobs.append(job_data)
                        
                    except Exception as e:
                        logger.error(f"{company_name}: Error extracting job details - {e}")

                if all_jobs:
                    try:
                        supabase.table("teamtailor_jobs_outline") \
                            .upsert(all_jobs, on_conflict="opening_link") \
                            .execute()
                        total_jobs += len(all_jobs)
                        logger.info(f"{company_name}: Page {current_page} - Found {len(all_jobs)} jobs (Total: {total_jobs})")
                    except Exception as e:
                        logger.error(f"{company_name}: Failed to upsert jobs - {e}")
                        break

                # Check for show_more button
                show_more_button = selector.xpath('//div[@id="show_more_button"]').get()
                if not show_more_button:
                    logger.info(f"{company_name}: Completed scraping - Found {total_jobs} jobs across {current_page} pages")
                    break
                
                current_page += 1
                logger.debug(f"{company_name}: Moving to page {current_page}")

            if total_jobs > 0:
                logger.info(f"✅ {company_name}: Completed scraping - Found {total_jobs} jobs across {current_page} pages")
            else:
                logger.warning(f"⚠️ {company_name}: No jobs found")

        except Exception as e:
            logger.error(f"❌ {company_name}: Failed to process - {e}")

async def main(careers_page_url: str, run_hash: str, url_id: int):
    try:
        supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )
        
        logger.info("🚀 Starting job scraping process")
        start_time = time.time()
        
        # Extract company name from URL
        company_name = careers_page_url.split('//')[1].split('.')[0]
        
        semaphore = asyncio.Semaphore(10)
        
        # Process the company
        async with aiohttp.ClientSession() as session:
            await process_company(
                session=session,
                semaphore=semaphore,
                url=careers_page_url,
                company_name=company_name,
                run_hash=run_hash,
                supabase=supabase,
                index=url_id,
                total_urls=1
            )
        
        end_time = time.time()
        duration = end_time - start_time
        logger.info(f"✨ Completed processing in {duration:.2f} seconds")

    except Exception as e:
        logger.error(f"❌ Script failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main(None, None, None))  # Default values for direct script execution
