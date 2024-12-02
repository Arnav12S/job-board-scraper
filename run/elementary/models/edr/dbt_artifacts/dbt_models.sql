
      
        
            delete from "postgres"."elementary"."dbt_models"
            where (
                unique_id) in (
                select (unique_id)
                from "dbt_models__dbt_tmp122502892848"
            );

        
    

    insert into "postgres"."elementary"."dbt_models" ("unique_id", "alias", "checksum", "materialization", "tags", "meta", "owner", "database_name", "schema_name", "depends_on_macros", "depends_on_nodes", "description", "name", "package_name", "original_path", "path", "patch_path", "generated_at", "metadata_hash", "unique_key", "incremental_strategy")
    (
        select "unique_id", "alias", "checksum", "materialization", "tags", "meta", "owner", "database_name", "schema_name", "depends_on_macros", "depends_on_nodes", "description", "name", "package_name", "original_path", "path", "patch_path", "generated_at", "metadata_hash", "unique_key", "incremental_strategy"
        from "dbt_models__dbt_tmp122502892848"
    )
  