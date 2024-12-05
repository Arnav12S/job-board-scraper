def set_initial_table_schema(spider_name):
    """
    Set Initial table schema, columns present in all tables.
    Removed `levergreen_id` as it's not used in jobvite_jobs_outline.
    """
    return f"""CREATE TABLE IF NOT EXISTS {spider_name} (
        id SERIAL PRIMARY KEY,
        created_at BIGINT,
        updated_at BIGINT,
        source TEXT,
        run_hash TEXT,
        raw_html_file_location TEXT,
        existing_html_used BOOLEAN
    """


def create_table_schema(table_name, initial_table_schema=""):
    if table_name == "greenhouse_job_departments":
        return initial_table_schema + """
        , company_name TEXT
        , department_category TEXT
        , department_id TEXT
        , department_name TEXT
    )
    """
    elif table_name == "greenhouse_jobs_outline":
        return initial_table_schema + """
        , department_ids TEXT
        , location TEXT
        , office_ids TEXT
        , opening_link TEXT
        , opening_title TEXT
    )
    """
    elif table_name == "lever_jobs_outline":
        return initial_table_schema + """
        , company_name TEXT
        , department_names TEXT
        , location TEXT
        , opening_link TEXT
        , opening_title TEXT
        , workplace_type TEXT
    )
    """
    elif table_name == "jobvite_jobs_outline":
        return initial_table_schema + """
        , company_name TEXT
        , department_names TEXT
        , location TEXT
        , opening_link TEXT
        , opening_title TEXT
        , workplace_type TEXT
    )
    """
    else:
        # Ensure all other tables are properly closed
        return initial_table_schema + ")"


def finalize_table_schema(table_name):
    initial_table_schema = set_initial_table_schema(table_name)
    return create_table_schema(table_name, initial_table_schema)


def finalize_value(item, value):
    try:
        return item[value]
    except KeyError:
        return None


def get_table_columns(table_name):
    initial_columns = """(source, run_hash, raw_html_file_location, existing_html_used"""
    if table_name == "greenhouse_job_departments":
        return initial_columns + """, company_name, department_category, department_id, department_name)"""
    elif table_name == "greenhouse_jobs_outline":
        return initial_columns + """, department_ids, location, office_ids, opening_link, opening_title)"""
    elif table_name == "lever_jobs_outline":
        return initial_columns + """, company_name, department_names, location, opening_link, opening_title, workplace_type)"""
    elif table_name == "jobvite_jobs_outline":
        return initial_columns + """, company_name, department_names, location, opening_link, opening_title, workplace_type)"""
    else:
        return initial_columns + ")"


def get_table_values(table_name, item):
    initial_values = [
        #finalize_value(item, "created_at"),
        #finalize_value(item, "updated_at"),
        finalize_value(item, "source"),
        finalize_value(item, "run_hash"),
        finalize_value(item, "raw_html_file_location"),
        finalize_value(item, "existing_html_used"),
    ]
    placeholder = ", ".join(["%s"] * len(initial_values))
    
    if table_name == "greenhouse_job_departments":
        additional_values = [
            finalize_value(item, "company_name"),
            finalize_value(item, "department_category"),
            finalize_value(item, "department_id"),
            finalize_value(item, "department_name"),
        ]
        placeholder += ", " + ", ".join(["%s"] * len(additional_values))
        initial_values += additional_values
    elif table_name == "greenhouse_jobs_outline":
        additional_values = [
            finalize_value(item, "department_ids"),
            finalize_value(item, "location"),
            finalize_value(item, "office_ids"),
            finalize_value(item, "opening_link"),
            finalize_value(item, "opening_title"),
        ]
        placeholder += ", " + ", ".join(["%s"] * len(additional_values))
        initial_values += additional_values
    elif table_name == "lever_jobs_outline":
        additional_values = [
            finalize_value(item, "company_name"),
            finalize_value(item, "department_names"),
            finalize_value(item, "location"),
            finalize_value(item, "opening_link"),
            finalize_value(item, "opening_title"),
            finalize_value(item, "workplace_type"),
        ]
        placeholder += ", " + ", ".join(["%s"] * len(additional_values))
        initial_values += additional_values
    elif table_name == "jobvite_jobs_outline":
        additional_values = [
            finalize_value(item, "company_name"),
            finalize_value(item, "department_names"),
            finalize_value(item, "location"),
            finalize_value(item, "opening_link"),
            finalize_value(item, "opening_title"),
            finalize_value(item, "workplace_type"),
        ]
        placeholder += ", " + ", ".join(["%s"] * len(additional_values))
        initial_values += additional_values

    return f"""({placeholder})""", initial_values


def create_insert_item(table_name, item):
    table_columns = get_table_columns(table_name)
    percent_s, table_values = get_table_values(table_name, item)
    return (
        f"""insert into {table_name} {table_columns} values {percent_s}""",
        table_values,
    )