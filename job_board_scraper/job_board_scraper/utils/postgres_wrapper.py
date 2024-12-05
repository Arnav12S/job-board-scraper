import os
import psycopg2


class PostgresWrapper:
    def __init__(self):
        ## Connection Details
        self.hostname = os.getenv("PG_HOST")
        self.username = os.getenv("PG_USER")
        self.password = os.getenv("PG_PASSWORD")
        self.database = os.getenv("PG_DATABASE")
        self.port = os.getenv("PG_PORT")

    def connection(self):
        ## Create/Connect to database
        connection_string = f"postgresql://{self.username}:{self.password}@{self.hostname}:{self.port}/{self.database}"
        return psycopg2.connect(connection_string)

    def cursor(self):
        ## Create cursor, used to execute commands
        return self.connection().cursor()