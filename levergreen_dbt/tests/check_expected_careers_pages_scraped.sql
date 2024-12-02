{{ 
    config(
        severity = 'error',
        warn_if = '>0'
    ) 
}}
--config must be of the bracket comment format or it doesn't comment it.

-- here we are checking if the scraper did correctly scrape jobs for each careers_page
-- If the scraper missed a page due to an unexpected error, we will have mismatches here

with expected_sources as (
    select distinct company_url as expected_source
    from {{ source('levergreen', 'job_board_urls') }}
    where is_enabled
),

actual_sources as (
    select distinct source as actual_source
    from {{ ref('active_job_postings') }}
)

select * from expected_sources
full outer join actual_sources on expected_sources.expected_source = actual_sources.actual_source
where expected_sources.expected_source is null or actual_sources.actual_source is null

WITH expected_sources AS (
    SELECT DISTINCT company_url as expected_source
    FROM job_board_urls
    WHERE is_enabled
),

actual_sources AS (
    SELECT DISTINCT source as actual_source 
    FROM active_job_postings
)

UPDATE job_board_urls
SET is_enabled = false
WHERE company_url IN (
    SELECT expected_source 
    FROM expected_sources
    LEFT JOIN actual_sources ON expected_sources.expected_source = actual_sources.actual_source
    WHERE actual_sources.actual_source IS NULL
);