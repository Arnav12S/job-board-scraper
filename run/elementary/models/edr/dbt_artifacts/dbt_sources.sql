
      
        
            delete from "postgres"."elementary"."dbt_sources"
            where (
                unique_id) in (
                select (unique_id)
                from "dbt_sources__dbt_tmp124851196852"
            );

        
    

    insert into "postgres"."elementary"."dbt_sources" ("unique_id", "database_name", "schema_name", "source_name", "name", "identifier", "loaded_at_field", "freshness_warn_after", "freshness_error_after", "freshness_filter", "freshness_description", "relation_name", "tags", "meta", "owner", "package_name", "original_path", "path", "source_description", "description", "generated_at", "metadata_hash")
    (
        select "unique_id", "database_name", "schema_name", "source_name", "name", "identifier", "loaded_at_field", "freshness_warn_after", "freshness_error_after", "freshness_filter", "freshness_description", "relation_name", "tags", "meta", "owner", "package_name", "original_path", "path", "source_description", "description", "generated_at", "metadata_hash"
        from "dbt_sources__dbt_tmp124851196852"
    )
  