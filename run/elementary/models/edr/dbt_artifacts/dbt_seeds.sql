
      
        
            delete from "neondb"."elementary"."dbt_seeds"
            where (
                unique_id) in (
                select (unique_id)
                from "dbt_seeds__dbt_tmp093232350333"
            );

        
    

    insert into "neondb"."elementary"."dbt_seeds" ("unique_id", "alias", "checksum", "tags", "meta", "owner", "database_name", "schema_name", "description", "name", "package_name", "original_path", "path", "generated_at", "metadata_hash")
    (
        select "unique_id", "alias", "checksum", "tags", "meta", "owner", "database_name", "schema_name", "description", "name", "package_name", "original_path", "path", "generated_at", "metadata_hash"
        from "dbt_seeds__dbt_tmp093232350333"
    )
  