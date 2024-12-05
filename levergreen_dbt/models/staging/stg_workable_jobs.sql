with source as (
    select *
    from {{ source('raw', 'workable_jobs') }}
),

renamed as (
    select
        id,
        job_title,
        location,
        job_url,
        employment_type,
        spider_id,
        updated_at,
        source,
        company_name,
        run_hash,
        raw_html_file_location,
        existing_html_used
    from source
)

select * from renamed