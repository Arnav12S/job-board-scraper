
      
        
            delete from "neondb"."elementary"."schema_columns_snapshot"
            where (
                column_state_id) in (
                select (column_state_id)
                from "schema_columns_snapshot__dbt_tmp095309203466"
            );

        
    

    insert into "neondb"."elementary"."schema_columns_snapshot" ("column_state_id", "full_column_name", "full_table_name", "column_name", "data_type", "is_new", "detected_at", "created_at")
    (
        select "column_state_id", "full_column_name", "full_table_name", "column_name", "data_type", "is_new", "detected_at", "created_at"
        from "schema_columns_snapshot__dbt_tmp095309203466"
    )
  