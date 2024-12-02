
      
        
            delete from "postgres"."elementary"."dbt_columns"
            where (
                unique_id) in (
                select (unique_id)
                from "dbt_columns__dbt_tmp124845136249"
            );

        
    

    insert into "postgres"."elementary"."dbt_columns" ("unique_id", "parent_unique_id", "name", "data_type", "tags", "meta", "database_name", "schema_name", "table_name", "description", "resource_type", "generated_at", "metadata_hash")
    (
        select "unique_id", "parent_unique_id", "name", "data_type", "tags", "meta", "database_name", "schema_name", "table_name", "description", "resource_type", "generated_at", "metadata_hash"
        from "dbt_columns__dbt_tmp124845136249"
    )
  