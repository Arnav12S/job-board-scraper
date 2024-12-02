select active_job_postings.* from "postgres"."core"."active_job_postings" active_job_postings
inner join "postgres"."public"."job_board_urls" job_board_urls 
    on active_job_postings.source = job_board_urls.company_url
where job_board_urls.is_prospect