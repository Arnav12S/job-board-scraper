import scrapy
import json
from scrapy.loader import ItemLoader
from job_board_scraper.items import TeamTailorJobsOutlineItem
from job_board_scraper.spiders.greenhouse_jobs_outline_spider import GreenhouseJobsOutlineSpider
from dotenv import load_dotenv

load_dotenv()

class WorkableJobsOutlineSpider(GreenhouseJobsOutlineSpider):
    name = "workable_jobs_outline"
    allowed_domains = ["apply.workable.com"]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spider_id = kwargs.pop("spider_id", 7)
        # Extract company shortname from URL (e.g., 'techflow' from 'apply.workable.com/techflow/')
        self.company_shortname = self.careers_page_url.strip('/').split('/')[-1]
        self.api_url = f"https://apply.workable.com/api/v3/accounts/{self.company_shortname}/jobs"
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://apply.workable.com',
            'Referer': self.careers_page_url,
            'Accept-Language': 'en',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        self.logger.info(f"Initialized Spider for company: {self.company_shortname}")

    def start_requests(self):
        # Initial request without token
        payload = {
            "query": "",
            "department": [],
            "location": [],
            "remote": [],
            "workplace": [],
            "worktype": []
        }
        
        yield scrapy.Request(
            url=self.api_url,
            method='POST',
            headers=self.headers,
            body=json.dumps(payload),
            callback=self.parse_jobs,
            meta={'dont_retry': True}
        )

    def parse_jobs(self, response):
        try:
            data = json.loads(response.text)
            jobs = data.get('results', [])
            
            for job in jobs:
                il = ItemLoader(item=TeamTailorJobsOutlineItem())
                
                # Extract job details
                il.add_value('job_title', job.get('title'))
                il.add_value('location', self._format_location(job))
                il.add_value('job_url', f"{self.careers_page_url}j/{job.get('shortcode')}")
                il.add_value('employment_type', job.get('type'))
                
                # Add standard fields
                il.add_value("spider_id", self.spider_id)
                il.add_value("updated_at", self.updated_at)
                il.add_value("source", self.html_source)
                il.add_value("company_name", self.company_name)
                il.add_value("run_hash", self.run_hash)
                il.add_value("raw_html_file_location", self.full_s3_html_path)
                il.add_value("existing_html_used", self.existing_html_used)
                
                yield il.load_item()
            
            # Handle pagination
            next_page_token = data.get('nextPage')
            if next_page_token:
                payload = {
                    "query": "",
                    "token": next_page_token,
                    "department": [],
                    "location": [],
                    "remote": [],
                    "workplace": [],
                    "worktype": []
                }
                
                yield scrapy.Request(
                    url=self.api_url,
                    method='POST',
                    headers=self.headers,
                    body=json.dumps(payload),
                    callback=self.parse_jobs,
                    meta={'dont_retry': True}
                )
                
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error: {e}")
        except Exception as e:
            self.logger.error(f"Error in parse_jobs: {e}", exc_info=True)

    def _format_location(self, job):
        """Format location information from job data"""
        try:
            location_data = []
            
            # Add city if available
            if job.get('city'):
                location_data.append(job['city'])
            
            # Add region if available
            if job.get('region'):
                location_data.append(job['region'])
                
            # Add country if available
            if job.get('country'):
                location_data.append(job['country'])
                
            # Handle remote locations
            if job.get('remote', False):
                location_data.append('Remote')
                
            return ', '.join(filter(None, location_data))
            
        except Exception as e:
            self.logger.error(f"Error formatting location: {e}")
            return '' 