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
from postgrest.exceptions import APIError

import os
import boto3
import logging

logger = logging.getLogger("logger")


class JobScraperPipelinePostgres:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing JobScraperPipelinePostgres")
        
        # Load environment variables
        load_dotenv()
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
        
        try:
            # Try to select from table to check if it exists
            self.supabase.table(self.table_name).select("*").limit(1).execute()
        except APIError as e:
            if 'relation "public.' in str(e):
                self.logger.info(f"Creating table {self.table_name}")
                try:
                    # Create table using the schema from utils
                    table_schema = pipline_util.finalize_table_schema(self.table_name)
                    self.supabase.rpc('exec_sql', {'query': table_schema}).execute()
                    self.logger.info(f"Successfully created table {self.table_name}")
                except Exception as create_error:
                    self.logger.error(f"Failed to create table {self.table_name}: {create_error}")
                    raise

    def process_item(self, item, spider):
        self.logger.info(f"Processing item in pipeline: {item}")
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
            
            # Extract column names by splitting the insert statement
            columns_part = insert_item_statement.split('(')[1].split(')')[0]
            columns = [col.strip() for col in columns_part.split(',')]
            data_dict = dict(zip(columns, table_values))
            
            # Insert using Supabase
            response = self.supabase.table(self.table_name).insert(data_dict).execute()
            if response.status_code in [200, 201]:
                self.logger.info(f"Successfully inserted item into {self.table_name}")
            else:
                self.logger.error(f"Failed to insert item into {self.table_name}: {response}")
        
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
