
      
        
            delete from "postgres"."elementary"."dbt_metrics"
            where (
                unique_id) in (
                select (unique_id)
                from "dbt_metrics__dbt_tmp121314166714"
            );

        
    

    insert into "postgres"."elementary"."dbt_metrics" ("unique_id", "name", "label", "model", "type", "sql", "timestamp", "filters", "time_grains", "dimensions", "depends_on_macros", "depends_on_nodes", "description", "tags", "meta", "package_name", "original_path", "path", "generated_at", "metadata_hash")
    (
        select "unique_id", "name", "label", "model", "type", "sql", "timestamp", "filters", "time_grains", "dimensions", "depends_on_macros", "depends_on_nodes", "description", "tags", "meta", "package_name", "original_path", "path", "generated_at", "metadata_hash"
        from "dbt_metrics__dbt_tmp121314166714"
    )
  