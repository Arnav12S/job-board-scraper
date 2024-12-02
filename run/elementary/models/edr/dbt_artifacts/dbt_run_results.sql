
      
        
            delete from "postgres"."elementary"."dbt_run_results"
            where (
                model_execution_id) in (
                select (model_execution_id)
                from "dbt_run_results__dbt_tmp122503053999"
            );

        
    

    insert into "postgres"."elementary"."dbt_run_results" ("model_execution_id", "unique_id", "invocation_id", "generated_at", "created_at", "name", "message", "status", "resource_type", "execution_time", "execute_started_at", "execute_completed_at", "compile_started_at", "compile_completed_at", "rows_affected", "full_refresh", "compiled_code", "failures", "query_id", "thread_id", "materialization", "adapter_response")
    (
        select "model_execution_id", "unique_id", "invocation_id", "generated_at", "created_at", "name", "message", "status", "resource_type", "execution_time", "execute_started_at", "execute_completed_at", "compile_started_at", "compile_completed_at", "rows_affected", "full_refresh", "compiled_code", "failures", "query_id", "thread_id", "materialization", "adapter_response"
        from "dbt_run_results__dbt_tmp122503053999"
    )
  