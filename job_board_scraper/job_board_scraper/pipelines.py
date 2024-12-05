# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

from itemadapter import ItemAdapter
from job_board_scraper.utils import pipline_util
from job_board_scraper.utils.postgres_wrapper import PostgresWrapper
import logging

logger = logging.getLogger("logger")

class JobScraperPipelinePostgres:
    def __init__(self):
        logger.info("Initializing JobScraperPipelinePostgres")
        PostgresWrapper.initialize_pool(minconn=1, maxconn=20)

    def open_spider(self, spider):
        self.table_name = spider.name
        initial_table_schema = pipline_util.set_initial_table_schema(self.table_name)
        create_table_statement = pipline_util.create_table_schema(
            self.table_name, initial_table_schema
        )
        
        cursor, conn = PostgresWrapper.get_cursor()
        try:
            logger.info(f"Creating table with statement: {create_table_statement}")
            cursor.execute(create_table_statement)
            conn.commit()
            logger.info(f"Successfully created/verified table {self.table_name}")
        except Exception as e:
            logger.error(f"Error creating table: {e}")
            conn.rollback()
            raise
        finally:
            cursor.close()
            PostgresWrapper.release_connection(conn)

    def process_item(self, item, spider):
        logger.info(f"Processing item in pipeline for spider {spider.name}")
        if not item:
            logger.error("Received empty item")
            return item
        
        cursor, conn = PostgresWrapper.get_cursor()
        try:
            insert_item_statement, table_values_list = pipline_util.create_insert_item(
                self.table_name, item
            )
            logger.info(f"Attempting to execute SQL: {insert_item_statement}")
            logger.info(f"With values: {table_values_list}")
            
            if not table_values_list:
                logger.error("No values to insert")
                return item
                
            cursor.execute(insert_item_statement, tuple(table_values_list))
            conn.commit()
            logger.info(f"Successfully inserted item into {self.table_name}")
            
        except Exception as e:
            logger.error(f"Failed to insert item: {str(e)}")
            logger.error(f"Item contents: {dict(item)}")
            conn.rollback()
        finally:
            cursor.close()
            PostgresWrapper.release_connection(conn)
        
        return item

    def close_spider(self, spider):
        try:
            PostgresWrapper.close_all_connections()
            logger.info("PostgreSQL connection pool closed.")
        except Exception as e:
            logger.error(f"Error closing connection pool: {e}")

    #def export_html(self, item):
    ##    try:
    ##        html_content = item.get('html_content')
    ##        url = item.get('url')
    ##        if html_content and url:
    ##            object_key = f"html/{self._generate_object_key(url)}.html"
    ##            self.s3_client.put_object(
    ##                Bucket=self.raw_html_s3_bucket,
    ##                Key=object_key,
    ##                Body=html_content.encode('utf-8'),
    ##                ContentType='text/html'
    ##            )
    ##            logging.info(f"Exported HTML to s3://{self.raw_html_s3_bucket}/{object_key}")
    ##    except Exception as e:
    #        logging.error(f"Failed to export HTML to S3: {e}")

    def _generate_object_key(self, url):
        return url.replace("https://", "").replace("/", "_")