with convert_unix_to_ts as (
    select 
        *,
        to_timestamp(created_at) at time zone 'UTC' as created_at_utc,
        to_timestamp(updated_at) at time zone 'UTC' as updated_at_utc
    from "postgres"."public"."ashby_jobs_outline"
),

convert_ts_to_date as (
    select
        *,
        date(created_at_utc) as created_date_utc,
        date(updated_at_utc) as updated_date_utc,
        row_number() over(
            partition by levergreen_id
            order by
                updated_at
        ) as earliest_levergreen_id_row
    from convert_unix_to_ts
),

ashby_outlines_by_levergreen_id as (
    select
        *,
        'ashby' as job_board,
        cast(existing_json_used as boolean) as uses_existing,
        row_number() over(
            partition by opening_link, updated_date_utc
            order by
                updated_at
        ) as earliest_opening_link_row
    from convert_ts_to_date
    where earliest_levergreen_id_row = 1
)

select
    concat(job_board,'_',id) as id,
    levergreen_id,
    created_at_utc,
    updated_at_utc,
    created_date_utc,
    updated_date_utc,
    ashby_job_board_source as source,
    uses_existing,
    raw_json_file_location,
    run_hash,
    company_name,
    opening_id,
    opening_name as opening_title,
    department_id, 
    location_id, 
    location_name, 
    employment_type, 
    compensation_tier,
    opening_link as full_opening_link,
    job_board
from
    ashby_outlines_by_levergreen_id
where
    earliest_opening_link_row = 1