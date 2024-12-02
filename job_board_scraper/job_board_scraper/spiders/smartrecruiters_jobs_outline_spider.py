import scrapy
import json
from scrapy.loader import ItemLoader
from job_board_scraper.items import TeamTailorJobsOutlineItem
from job_board_scraper.spiders.greenhouse_jobs_outline_spider import GreenhouseJobsOutlineSpider
from dotenv import load_dotenv

load_dotenv()

class SmartRecruitersJobsOutlineSpider(GreenhouseJobsOutlineSpider):
    name = "smartrecruiters_jobs_outline"
    allowed_domains = ["careers.smartrecruiters.com"]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spider_id = kwargs.pop("spider_id", 5)
        self.company_id = self.careers_page_url.split('/')[-1]
        self.start_urls = [self.careers_page_url]
        self.current_page = 0
        self.headers = {
            'Accept': '*/*',
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': self.careers_page_url
        }
        self.logger.info(f"Initialized Spider with URL: {self.start_urls[0]}")

    def start_requests(self):
        # First request to get the initial page
        yield scrapy.Request(
            url=self.start_urls[0],
            callback=self.parse_initial_page,
            headers=self.headers,
            meta={'dont_retry': True}
        )

    def parse_initial_page(self, response):
        # Parse the initial HTML page
        yield from self.parse_jobs(response)
        
        # Start the AJAX pagination requests
        api_url = f"{response.url}/api/groups"
        yield scrapy.Request(
            url=f"{api_url}?page={self.current_page}",
            callback=self.parse_ajax_pages,
            headers=self.headers,
            meta={'api_url': api_url, 'dont_retry': True}
        )

    def parse_ajax_pages(self, response):
        try:
            data = json.loads(response.text)
            if not data or not data.get('content'):
                return

            # Parse jobs from AJAX response
            for section in data['content']:
                location = section.get('title', '')
                for job in section.get('jobs', []):
                    il = ItemLoader(item=TeamTailorJobsOutlineItem())
                    
                    il.add_value('job_title', job.get('title'))
                    il.add_value('location', location)
                    il.add_value('job_url', job.get('url'))
                    il.add_value('department', job.get('department', ''))
                    il.add_value('employment_type', job.get('type', 'Full-time'))
                    
                    # Add standard fields
                    il.add_value("spider_id", self.spider_id)
                    il.add_value("updated_at", self.updated_at)
                    il.add_value("source", self.html_source)
                    il.add_value("company_name", self.company_name)
                    il.add_value("run_hash", self.run_hash)
                    il.add_value("raw_html_file_location", self.full_s3_html_path)
                    il.add_value("existing_html_used", self.existing_html_used)
                    
                    yield il.load_item()

            # Check if there are more pages
            if data.get('hasNext', False):
                self.current_page += 1
                api_url = response.meta['api_url']
                yield scrapy.Request(
                    url=f"{api_url}?page={self.current_page}",
                    callback=self.parse_ajax_pages,
                    headers=self.headers,
                    meta={'api_url': api_url, 'dont_retry': True}
                )

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error: {e}")
        except Exception as e:
            self.logger.error(f"Error in parse_ajax_pages: {e}", exc_info=True)

    def parse_jobs(self, response):
        try:
            # Parse jobs from the initial HTML page
            job_sections = response.xpath('//section[contains(@class, "openings-section")]')
            
            for section in job_sections:
                location = section.xpath('.//h3[contains(@class, "opening-title")]/text()').get('')
                jobs = section.xpath('.//li[contains(@class, "opening-job")]')
                
                for job in jobs:
                    il = ItemLoader(item=TeamTailorJobsOutlineItem())
                    
                    job_link = job.xpath('.//a[contains(@class, "link--block")]')
                    il.add_value('job_title', job_link.xpath('.//h4/text()').get())
                    il.add_value('location', location)
                    il.add_value('job_url', job_link.xpath('@href').get())
                    il.add_value('employment_type', 
                        job.xpath('.//span[contains(@class, "margin--right--s")]/text()').get('Full-time'))
                    
                    # Add standard fields
                    il.add_value("spider_id", self.spider_id)
                    il.add_value("updated_at", self.updated_at)
                    il.add_value("source", self.html_source)
                    il.add_value("company_name", self.company_name)
                    il.add_value("run_hash", self.run_hash)
                    il.add_value("raw_html_file_location", self.full_s3_html_path)
                    il.add_value("existing_html_used", self.existing_html_used)
                    
                    yield il.load_item()
                    
        except Exception as e:
            self.logger.error(f"Error in parse_jobs: {e}", exc_info=True) 