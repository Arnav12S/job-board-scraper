-- Create tables for each job board
CREATE TABLE IF NOT EXISTS public.workable_jobs (
    id SERIAL PRIMARY KEY,
    job_title TEXT NOT NULL,
    location TEXT,
    job_url TEXT UNIQUE NOT NULL,
    employment_type TEXT,
    spider_id INTEGER NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE,
    source TEXT,
    company_name TEXT,
    run_hash TEXT,
    raw_html_file_location TEXT,
    existing_html_used BOOLEAN
);

-- Create similar tables for other job boards
CREATE TABLE IF NOT EXISTS public.jobvite_jobs (...);
CREATE TABLE IF NOT EXISTS public.recruitee_jobs (...);
CREATE TABLE IF NOT EXISTS public.smartrecruiters_jobs (...); 