import scrapy
from scrapy.loader import ItemLoader
from scrapy.selector import Selector
from job_board_scraper.items import TeamTailorJobsOutlineItem
from job_board_scraper.spiders.greenhouse_jobs_outline_spider import GreenhouseJobsOutlineSpider
from dotenv import load_dotenv

load_dotenv()

class TeamTailorJobsOutlineSpider(GreenhouseJobsOutlineSpider):
    name = "teamtailor_jobs_outline"
    allowed_domains = ["careers.whitestuff.com"]  # Adjust based on the company

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spider_id = kwargs.pop("spider_id", 4)
        self.start_urls = [self.careers_page_url]
        self.current_page = 1
        self.logger.info(f"Initialized Spider with URL: {self.start_urls[0]}")

    def start_requests(self):
        self.logger.info(f"Starting requests with URLs: {self.start_urls}")
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                errback=self.errback_httpbin,
                dont_filter=True,
                meta={'dont_retry': True}
            )

    def parse(self, response):
        try:
            self.logger.info(f"Parsing response from URL: {response.url}")
            response_html = self.finalize_response(response)
            selector = Selector(text=response_html, type="html")
            
            # Find all job listings
            job_listings = selector.xpath('//ul[@id="jobs_list_container"]/li')
            self.logger.info(f"Found {len(job_listings)} job listings")

            for i, job in enumerate(job_listings):
                try:
                    il = ItemLoader(
                        item=TeamTailorJobsOutlineItem(),
                        selector=job
                    )
                    
                    # Extract job details
                    il.add_xpath("opening_title", './/span[@class="text-block-base-link company-link-style"]/text()')
                    il.add_xpath("opening_link", './/a/@href')
                    
                    # Extract location and department
                    location_dept = job.xpath('.//span[@class="text-base"]/span/text()').getall()
                    if location_dept:
                        # Filter out separator dots
                        location_dept = [x.strip() for x in location_dept if x.strip() != "·"]
                        
                        if len(location_dept) >= 1:
                            il.add_value("department_names", location_dept[0])
                        if len(location_dept) >= 2:
                            il.add_value("location", location_dept[1])
                            
                    # Check for remote work
                    remote_indicator = job.xpath('.//span[contains(text(), "Hybrid Remote")]')
                    if remote_indicator:
                        il.add_value("workplace_type", "Hybrid Remote")
                    
                    # Add required fields
                    row_id = self.determine_row_id(i)
                    il.add_value("id", row_id)
                    il.add_value("created_at", self.created_at)
                    il.add_value("updated_at", self.updated_at)
                    il.add_value("source", self.html_source)
                    il.add_value("company_name", self.company_name)
                    il.add_value("run_hash", self.run_hash)
                    il.add_value("raw_html_file_location", self.full_s3_html_path)
                    il.add_value("existing_html_used", self.existing_html_used)
                    
                    item = il.load_item()
                    if not any(item.values()):
                        self.logger.warning(f"Item has no values: {dict(item)}")
                        continue
                    yield item
                    
                except Exception as e:
                    self.logger.error(f"Error processing job listing {i}: {e}")
            
            # Handle pagination
            next_page = selector.xpath('//a[@id="show_more_button"]/@href').get()
            if next_page:
                self.current_page += 1
                next_url = response.urljoin(next_page)
                yield scrapy.Request(
                    url=next_url,
                    callback=self.parse,
                    meta={'dont_retry': True}
                )
                
        except Exception as e:
            self.logger.error(f"Error in parse method: {e}", exc_info=True)

    def errback_httpbin(self, failure):
        self.logger.error(f"Request failed: {failure.value}")
