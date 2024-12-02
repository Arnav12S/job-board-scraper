
      
        
            delete from "postgres"."elementary"."dbt_invocations"
            where (
                invocation_id) in (
                select (invocation_id)
                from "dbt_invocations__dbt_tmp124431640062"
            );

        
    

    insert into "postgres"."elementary"."dbt_invocations" ("invocation_id", "job_id", "job_name", "job_run_id", "run_started_at", "run_completed_at", "generated_at", "created_at", "command", "dbt_version", "elementary_version", "full_refresh", "invocation_vars", "vars", "target_name", "target_database", "target_schema", "target_profile_name", "threads", "selected", "yaml_selector", "project_id", "project_name", "env", "env_id", "cause_category", "cause", "pull_request_id", "git_sha", "orchestrator", "dbt_user", "job_url", "job_run_url", "account_id", "target_adapter_specific_fields")
    (
        select "invocation_id", "job_id", "job_name", "job_run_id", "run_started_at", "run_completed_at", "generated_at", "created_at", "command", "dbt_version", "elementary_version", "full_refresh", "invocation_vars", "vars", "target_name", "target_database", "target_schema", "target_profile_name", "threads", "selected", "yaml_selector", "project_id", "project_name", "env", "env_id", "cause_category", "cause", "pull_request_id", "git_sha", "orchestrator", "dbt_user", "job_url", "job_run_url", "account_id", "target_adapter_specific_fields"
        from "dbt_invocations__dbt_tmp124431640062"
    )
  