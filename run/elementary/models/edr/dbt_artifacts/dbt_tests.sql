
      
        
            delete from "neondb"."elementary"."dbt_tests"
            where (
                unique_id) in (
                select (unique_id)
                from "dbt_tests__dbt_tmp095308599631"
            );

        
    

    insert into "neondb"."elementary"."dbt_tests" ("unique_id", "database_name", "schema_name", "name", "short_name", "alias", "test_column_name", "severity", "warn_if", "error_if", "test_params", "test_namespace", "test_original_name", "tags", "model_tags", "model_owners", "meta", "depends_on_macros", "depends_on_nodes", "parent_model_unique_id", "description", "package_name", "type", "original_path", "path", "generated_at", "metadata_hash", "quality_dimension")
    (
        select "unique_id", "database_name", "schema_name", "name", "short_name", "alias", "test_column_name", "severity", "warn_if", "error_if", "test_params", "test_namespace", "test_original_name", "tags", "model_tags", "model_owners", "meta", "depends_on_macros", "depends_on_nodes", "parent_model_unique_id", "description", "package_name", "type", "original_path", "path", "generated_at", "metadata_hash", "quality_dimension"
        from "dbt_tests__dbt_tmp095308599631"
    )
  