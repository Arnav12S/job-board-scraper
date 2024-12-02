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
from supabase import create_client, Client

import os
import boto3
import logging

logger = logging.getLogger("logger")


class JobScraperPipelinePostgres:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing JobScraperPipelinePostgres")
        
        # Log environment variables (excluding sensitive info)
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        
        try:
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
            self.logger.info("Successfully connected to Supabase")
        except Exception as e:
            self.logger.error(f"Failed to connect to Supabase: {e}")
            raise

    def open_spider(self, spider):
        self.logger.info(f"Opening spider {spider.name}")
        self.table_name = spider.name
        self.logger.info(f"Using table name: {self.table_name}")
        
        # Create table if it doesn't exist
        initial_table_schema = pipline_util.set_initial_table_schema(self.table_name)
        create_table_statement = pipline_util.create_table_schema(
            self.table_name, initial_table_schema
        )
        
        try:
            # Execute raw SQL using Supabase
            self.supabase.table(self.table_name).select("*").limit(1).execute()
            self.logger.info(f"Table {self.table_name} exists")
        except Exception as e:
            self.logger.info(f"Creating table {self.table_name}")
            self.supabase.rpc('exec_sql', {'query': create_table_statement}).execute()

    def process_item(self, item, spider):
        self.logger.info(f"Processing item in pipeline for spider {spider.name}")
        if not item:
            self.logger.error("Received empty item")
            return item
        
        try:
            insert_item_statement, table_values = pipline_util.create_insert_item(
                self.table_name, item
            )
            
            if not table_values:
                self.logger.error("No values to insert")
                return item
            
            # Convert list to dict for Supabase insert
            columns = [col.split('$')[1].strip('}') for col in insert_item_statement.split('(')[1].split(')')[0].split(',')]
            data_dict = dict(zip(columns, table_values))
            
            # Insert using Supabase
            self.supabase.table(self.table_name).insert(data_dict).execute()
            self.logger.info(f"Successfully inserted item into {self.table_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to insert item: {str(e)}")
            self.logger.error(f"Item contents: {dict(item)}")
        
        return item

    def close_spider(self, spider):
        self.logger.info("Spider closed")

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
