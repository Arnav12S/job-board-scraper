# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
from job_board_scraper.utils import pipline_util
from io import BytesIO
from dotenv import load_dotenv
from botocore.exceptions import ClientError
from supabase import create_client
from postgrest.exceptions import APIError

import os
import boto3
import logging
import time

logger = logging.getLogger("logger")


class JobScraperPipelinePostgres:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing JobScraperPipelinePostgres")
        
        # Load environment variables
        load_dotenv()
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL or SUPABASE_KEY environment variables are not set")
        
        try:
            self.supabase = create_client(self.supabase_url, self.supabase_key)
            self.logger.info("Successfully connected to Supabase")
        except Exception as e:
            self.logger.error(f"Failed to connect to Supabase: {e}")
            raise

    def open_spider(self, spider):
        self.table_name = spider.name
        # Create table using utility function
        initial_table_schema = pipline_util.set_initial_table_schema(self.table_name)
        create_table_statement = pipline_util.create_table_schema(
            self.table_name, initial_table_schema
        )
        # Execute create table via Supabase
        try:
            self.supabase.table(self.table_name).select("*").limit(1).execute()
        except APIError:
            # Table doesn't exist, create it using RPC call or migration
            # Note: You'll need to implement the actual table creation logic
            # as Supabase doesn't support direct CREATE TABLE statements
            self.logger.warning(f"Table {self.table_name} doesn't exist")
            pass

    def process_item(self, item, spider):
        try:
            # Use utility function to get insert statement and values
            insert_item_statement, table_values_list = pipline_util.create_insert_item(
                self.table_name, item
            )
            # Convert to dictionary for Supabase insert
            data_dict = dict(zip(item.keys(), table_values_list))
            
            response = self.supabase.table(self.table_name).insert(data_dict).execute()
            self.logger.info(f"Successfully inserted item into {self.table_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to insert item: {e}")
            self.logger.error(f"Item contents: {dict(item)}")
        
        return item

    def close_spider(self, spider):
        self.logger.info(f"Closing spider {spider.name}")

    def export_html(self, item):
        try:
            html_content = item.get('html_content')
            url = item.get('url')
            if html_content and url:
                object_key = f"html/{self._generate_object_key(url)}.html"
                self.s3_client.put_object(
                    Bucket=self.raw_html_s3_bucket,
                    Key=object_key,
                    Body=html_content.encode('utf-8'),
                    ContentType='text/html'
                )
                logging.info(f"Exported HTML to s3://{self.raw_html_s3_bucket}/{object_key}")
        except Exception as e:
            logging.error(f"Failed to export HTML to S3: {e}")

    def _generate_object_key(self, url):
        return url.replace("https://", "").replace("/", "_")
