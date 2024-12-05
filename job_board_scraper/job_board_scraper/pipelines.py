# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
from job_board_scraper.utils import pipline_util
from supabase import create_client, Client
from dotenv import load_dotenv
import os
import logging

logger = logging.getLogger("logger")

class JobScraperPipelineSupabase:
    def __init__(self):
        load_dotenv()
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")

        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL or SUPABASE_KEY environment variables are not set")

        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)

    def open_spider(self, spider):
        self.table_name = spider.name
        initial_table_schema = pipline_util.set_initial_table_schema(self.table_name)
        create_table_statement = pipline_util.create_table_schema(self.table_name, initial_table_schema)
        
        # Supabase does not support direct SQL execution for schema changes, so ensure your tables are pre-created
        logger.info(f"Ensure table {self.table_name} exists with the correct schema.")

    def process_item(self, item, spider):
        try:
            insert_item_statement, table_values_list = pipline_util.create_insert_item(self.table_name, item)
            # Supabase client does not execute raw SQL, so we need to use the upsert method
            data = dict(zip(table_values_list, item))
            response = self.supabase.table(self.table_name).upsert(data).execute()
            if hasattr(response, 'error') and response.error:
                logger.error(f"Error upserting data: {response.error}")
            else:
                logger.info(f"Successfully inserted item into {self.table_name}")
        except Exception as e:
            logger.error(f"Failed to insert item: {e}")
            logger.error(f"Item contents: {dict(item)}")
        
        return item

    def close_spider(self, spider):
        logger.info(f"Closing spider {spider.name}")
