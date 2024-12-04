def get_url_chunks(careers_page_urls, chunk_size):
    # Ensure each item in careers_page_urls is a dictionary with a 'url' key
    url_chunks = []
    for i in range(0, len(careers_page_urls), chunk_size):
        chunk = careers_page_urls[i:i + chunk_size]
        # Extract the 'url' from each dictionary in the chunk
        url_chunk = [url_dict['url'] for url_dict in chunk]
        url_chunks.append(url_chunk)
    return url_chunks