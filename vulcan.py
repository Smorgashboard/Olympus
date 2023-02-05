import requests
from bs4 import BeautifulSoup
import re
import concurrent.futures

start_url = "http://example.com"
domain = "example.com"
visited_urls = set()
js_files = set()

def crawl(url):
    if url in visited_urls:
        return
    visited_urls.add(url)

    if not re.match(r"^https?://[\w-]*\.{}".format(domain), url):
        return

    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    scripts = soup.find_all("script")

    for script in scripts:
        src = script.get("src")
        if src and src.endswith(".js"):
            js_files.add(src)

    links = [link.get("href") for link in soup.find_all("a")]
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_link = {executor.submit(crawl, link): link for link in links if link.startswith("http")}

crawl(start_url)

def download_file(js_file):
    response = requests.get(js_file)
    with open(js_file.split("/")[-1], "wb") as f:
        f.write(response.content)

with concurrent.futures.ThreadPoolExecutor() as executor:
    future_to_file = {executor.submit(download_file, js_file): js_file for js_file in js_files}
    for future in concurrent.futures.as_completed(future_to_file):
        file = future_to_file[future]
        try:
            future.result()
            print(f"Downloaded {file}")
        except Exception as exc:
            print(f"{file} generated an exception: {exc}")
