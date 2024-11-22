
      
        
            delete from "neondb"."elementary"."data_monitoring_metrics"
            where (
                id) in (
                select (id)
                from "data_monitoring_metrics__dbt_tmp113604842506"
            );

        
    

    insert into "neondb"."elementary"."data_monitoring_metrics" ("id", "full_table_name", "column_name", "metric_name", "metric_type", "metric_value", "source_value", "bucket_start", "bucket_end", "bucket_duration_hours", "updated_at", "dimension", "dimension_value", "metric_properties", "created_at")
    (
        select "id", "full_table_name", "column_name", "metric_name", "metric_type", "metric_value", "source_value", "bucket_start", "bucket_end", "bucket_duration_hours", "updated_at", "dimension", "dimension_value", "metric_properties", "created_at"
        from "data_monitoring_metrics__dbt_tmp113604842506"
    )
  