import psycopg2
import scrapy
import json
import time
import os
from scrapy.loader import ItemLoader
from job_board_scraper.get_ashby_jobs import Posting
from job_board_scraper.items import TeamTailorJobsOutlineItem
from job_board_scraper.utils import general as util
from msgspec.json import decode
from msgspec import Struct
from datetime import datetime

class AshbyJobsOutlineSpider(scrapy.Spider):
    name = "ashby_jobs_outline"
    allowed_domains = ["jobs.ashbyhq.com"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spider_id = kwargs.pop("spider_id", 8)
        self.run_hash = util.hash_ids.encode(int(time.time()))
        self.pg_host = os.getenv("PG_HOST")
        self.pg_user = os.getenv("PG_USER")
        self.pg_pw = os.getenv("PG_PASSWORD")
        self.pg_db = os.getenv("PG_DATABASE")
        self.connection_string = f"postgresql://{self.pg_user}:{self.pg_pw}@{self.pg_host}/{self.pg_db}"
        self.ashby_api_endpoint = "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams"
        self.headers = {"Content-Type": "application/json"}

    def start_requests(self):
        # Connect to the database and fetch URLs
        connection = psycopg2.connect(
            host=self.pg_host,
            user=self.pg_user,
            password=self.pg_pw,
            dbname=self.pg_db,
        )
        cursor = connection.cursor()
        cursor.execute(os.getenv("ASHBY_PAGES_TO_SCRAPE_QUERY"))
        careers_page_urls = cursor.fetchall()
        cursor.close()
        connection.close()

        for i, url in enumerate(careers_page_urls):
            ashby_url = url[0]
            ashby_company = ashby_url.split("/")[-1].replace("%20", " ")
            variables = {"organizationHostedJobsPageName": ashby_company}
            yield scrapy.Request(
                url=self.ashby_api_endpoint,
                method='POST',
                headers=self.headers,
                body=json.dumps({"query": self.query, "variables": variables}),
                callback=self.parse_jobs,
                meta={'ashby_company': ashby_company, 'url_id': i}
            )

    def parse_jobs(self, response):
        ashby_company = response.meta['ashby_company']
        url_id = response.meta['url_id']
        response_json = json.loads(response.text)

        if response_json["data"]["jobBoard"] is None:
            self.logger.info(f"No data for {ashby_company}")
            return

        self.logger.info(f"Got data for {ashby_company}")

        try:
            posting_data = decode(
                json.dumps(response_json["data"]["jobBoard"]["jobPostings"]),
                type=list[Posting],
            )
        except TypeError:
            self.logger.error(
                f"An error occurred for company '{ashby_company}'. Perhaps you have the wrong Ashby company name"
            )
            return

        for j, record in enumerate(posting_data):
            il = ItemLoader(item=TeamTailorJobsOutlineItem())
            il.add_value("levergreen_id", util.hash_ids.encode(self.spider_id, url_id, j, int(time.time())))
            il.add_value("opening_id", record.id)
            il.add_value("opening_name", record.title)
            il.add_value("department_id", record.teamId)
            il.add_value("location_id", record.locationId)
            il.add_value("location_name", record.locationName)
            il.add_value("employment_type", record.employmentType)
            il.add_value("compensation_tier", record.compensationTierSummary)
            il.add_value("spider_id", self.spider_id)
            il.add_value("run_hash", self.run_hash)
            il.add_value("company_name", ashby_company)
            yield il.load_item() 