with workable_jobs as (
    select * from {{ ref('stg_workable_jobs') }}
),

jobvite_jobs as (
    select * from {{ ref('stg_jobvite_jobs') }}
),

recruitee_jobs as (
    select * from {{ ref('stg_recruitee_jobs') }}
),

smartrecruiters_jobs as (
    select * from {{ ref('stg_smartrecruiters_jobs') }}
),

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