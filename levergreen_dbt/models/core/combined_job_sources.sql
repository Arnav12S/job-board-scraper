with workable_jobs as (
    select * from {{ ref('stg_workable_jobs') }}
)

-- Keeping these commented out for future implementation
/*
, jobvite_jobs as (
    select * from 'stg_jobvite_jobs'
),

recruitee_jobs as (
    select * from 'stg_recruitee_jobs'
),

smartrecruiters_jobs as (
    select * from 'stg_smartrecruiters_jobs'
),
*/

select * from workable_jobs

-- When the other models are implemented, use this:
/*
combined_jobs as (
    select * from workable_jobs
    union all
    select * from jobvite_jobs
    union all
    select * from recruitee_jobs
    union all
    select * from smartrecruiters_jobs
)

select * from combined_jobs
*/ 