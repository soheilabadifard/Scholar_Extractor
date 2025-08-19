import os
import json
import requests
import time
from urllib.parse import quote
import bs4
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time as pytime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

## Change: Global setting to control headless mode
RUN_HEADLESS = False

CROSSREF_API = "https://api.crossref.org/works"
UNPAYWALL_API = "https://api.unpaywall.org/v2/"
UNPAYWALL_EMAIL = os.environ.get("UNPAYWALL_EMAIL", "abadifard@ksu.edu")

INPUT_JSON = "citations_obofoundryin2021operationalizingopendataprinciples.json"
PDF_DIR = "pdfs"
os.makedirs(PDF_DIR, exist_ok=True)


# --- Helper Function to Load Cookies into Selenium ---
def _load_cookies_into_driver(driver, url):
    """Loads cookies from cookies.json into the Selenium driver for the given URL's domain."""
    domain = get_domain_from_url(url)
    if not domain:
        return

    cookies = load_cookies()
    cookie_string = cookies.get(domain)

    driver.get(f"https://{domain}")

    if cookie_string:
        print(f"  Loading cookies for domain: {domain}")
        for cookie_pair in cookie_string.split(';'):
            if '=' in cookie_pair:
                name, value = cookie_pair.strip().split('=', 1)
                driver.add_cookie({'name': name, 'value': value, 'domain': domain})


# ---------------------------------------------------------


def get_doi_from_crossref(title, authors=None):
    params = {"query.title": title, "rows": 1}
    if authors:
        params["query.author"] = authors.split(",")[0]
    try:
        r = requests.get(CROSSREF_API, params=params, timeout=15)
        r.raise_for_status()
        items = r.json()["message"]["items"]
        if items:
            return items[0].get("DOI")
    except Exception as e:
        print(f"CrossRef error for '{title}': {e}")
    return None


def get_pdf_link_from_unpaywall(doi):
    url = f"{UNPAYWALL_API}{quote(doi)}?email={UNPAYWALL_EMAIL}"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        pdf_url = None
        if data:
            best_oa = data.get("best_oa_location")
            if best_oa:
                pdf_url = best_oa.get("url_for_pdf")
            if not pdf_url and "oa_locations" in data:
                for loc in data["oa_locations"]:
                    if loc.get("url_for_pdf"):
                        pdf_url = loc["url_for_pdf"]
                        break
        return pdf_url
    except Exception as e:
        print(f"Unpaywall error for DOI {doi}: {e}")
    return None


def get_pdf_link_from_semanticscholar(semantic_url):
    if not semantic_url or not isinstance(semantic_url, str) or not semantic_url.startswith('http'):
        print(f"Semantic Scholar error: Invalid or missing URL: {semantic_url}")
        return None
    try:
        r = requests.get(semantic_url, timeout=15)
        r.raise_for_status()
        soup = bs4.BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.endswith(".pdf") or "/pdf" in href:
                if href.startswith("/"):
                    base = "https://www.semanticscholar.org"
                    href = base + href
                return href
    except Exception as e:
        print(f"Semantic Scholar error for {semantic_url}: {e}")
    return None


def get_pdf_link_from_arxiv_biorxiv(article):
    venue = article.get("venue", "").lower()
    title = article.get("title", "")
    if "arxiv" in venue:
        url = article.get("url", "")
        if url and "arxiv.org" in url:
            for part in url.split("/"):
                if part.replace(".", "").isdigit():
                    return f"https://arxiv.org/pdf/{part}.pdf"
        doi = get_doi_from_crossref(title)
        if doi and doi.startswith("10.48550/arXiv."):
            return f"https://arxiv.org/pdf/{doi.split('arXiv.')[-1]}.pdf"
    if "biorxiv" in venue:
        doi = get_doi_from_crossref(title)
        if doi and doi.startswith("10.1101/"):
            return f"https://www.biorxiv.org/content/{doi}/full.pdf"
    return None


def get_pdf_link_from_publisher_page(doi):
    doi_url = f"https://doi.org/{doi}"
    try:
        r = requests.get(doi_url, timeout=15)
        r.raise_for_status()
        soup = bs4.BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.endswith(".pdf") or "/pdf" in href:
                if href.startswith("/"):
                    base = r.url.split("/", 3)[0:3]
                    href = "/".join(base) + href
                return href
    except Exception as e:
        print(f"Publisher page scraping error for DOI {doi}: {e}")

    try:
        chrome_options = uc.ChromeOptions()
        ## Change: Respects the global RUN_HEADLESS setting
        if RUN_HEADLESS:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        driver = uc.Chrome(options=chrome_options, version_main=138, browser_executable_path='/usr/bin/google-chrome')

        _load_cookies_into_driver(driver, doi_url)

        driver.get(doi_url)
        pytime.sleep(3)
        soup = bs4.BeautifulSoup(driver.page_source, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.endswith(".pdf") or "/pdf" in href:
                if href.startswith("/"):
                    base = driver.current_url.split("/", 3)[0:3]
                    href = "/".join(base) + href
                driver.quit()
                return href
        driver.quit()
    except Exception as e:
        print(f"Selenium publisher page scraping error for DOI {doi}: {e}")
    return None


def get_oup_article_url(pdf_url):
    if "/advance-article-pdf/doi/" in pdf_url:
        parts = pdf_url.split("/advance-article-pdf/doi/")
        base, doi = parts[0], parts[1].split("/")[0]
        return f"{base}/article/doi/{doi}"
    elif "/article-pdf/" in pdf_url:
        parts = pdf_url.split("/article-pdf/")
        base, doi = parts[0], parts[1].split("/")[0]
        return f"{base}/article/doi/{doi}"
    return None


def get_mdpi_article_url(pdf_url):
    return pdf_url[:-4] if pdf_url.endswith("/pdf") else None


def get_iop_article_url(pdf_url):
    return pdf_url[:-4] if "/article/" in pdf_url and pdf_url.endswith("/pdf") else None


def get_tandfonline_article_url(pdf_url):
    return pdf_url.replace("/doi/pdf/", "/doi/full/") if "/doi/pdf/" in pdf_url else None


def get_biorxiv_article_url(pdf_url):
    return pdf_url.replace("/full.pdf", "") if pdf_url.endswith("/full.pdf") else None


def get_arxiv_article_url(pdf_url):
    return pdf_url.replace("/pdf/", "/abs/").replace(".pdf", "") if "/pdf/" in pdf_url else None


def get_domain_from_url(url):
    try:
        return url.split("//")[1].split("/")[0]
    except Exception:
        return None


def load_cookies():
    cookies_path = "cookies.json"
    if os.path.exists(cookies_path):
        with open(cookies_path, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print("Warning: cookies.json is not valid JSON.")
                return {}
    return {}


def selenium_cookies_to_requests(driver):
    return {cookie['name']: cookie['value'] for cookie in driver.get_cookies()}


def download_pdf_selenium(pdf_url, filename):
    chrome_options = uc.ChromeOptions()
    ## Change: Respects the global RUN_HEADLESS setting
    if RUN_HEADLESS:
        chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    prefs = {"download.default_directory": os.path.abspath(PDF_DIR),
             "download.prompt_for_download": False,
             "plugins.always_open_pdf_externally": True}
    chrome_options.add_experimental_option("prefs", prefs)
    driver = uc.Chrome(options=chrome_options, version_main=138, browser_executable_path='/usr/bin/google-chrome')
    try:
        _load_cookies_into_driver(driver, pdf_url)

        existing_pdfs = set(os.listdir(PDF_DIR))
        driver.get(pdf_url)
        print(f"Selenium navigated to: {driver.current_url}")

        found_pdf = None
        for _ in range(60):
            current_pdfs = set(os.listdir(PDF_DIR))
            new_pdfs = [f for f in current_pdfs - existing_pdfs if f.endswith('.pdf')]
            if new_pdfs:
                found_pdf = new_pdfs[0]
                break
            pytime.sleep(0.5)

        if found_pdf:
            os.rename(os.path.join(PDF_DIR, found_pdf), filename)
            print(f"PDF found in download directory: {filename}")
            pytime.sleep(2)
            return True, None

        if driver.current_url.startswith('http') and driver.current_url.endswith('.pdf'):
            cookies = selenium_cookies_to_requests(driver)
            pdf_response = requests.get(driver.current_url, timeout=30, cookies=cookies)
            if pdf_response.status_code == 200 and pdf_response.headers.get('content-type', '').startswith(
                    'application/pdf'):
                with open(filename, 'wb') as pdf_file:
                    pdf_file.write(pdf_response.content)
                print(f"PDF saved using Selenium cookies: {filename}")
                pytime.sleep(2)
                return True, None

        print("PDF not found after Selenium download")
        return False, "PDF not found after Selenium download"
    except Exception as e:
        print(f"Selenium error: {e}")
        return False, str(e)
    finally:
        driver.quit()


def download_pdf(pdf_url, filename):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"}
    referer = None
    if "academic.oup.com" in pdf_url:
        referer = get_oup_article_url(pdf_url)
    elif "mdpi.com" in pdf_url:
        referer = get_mdpi_article_url(pdf_url)
    elif "iopscience.iop.org" in pdf_url:
        referer = get_iop_article_url(pdf_url)
    elif "tandfonline.com" in pdf_url:
        referer = get_tandfonline_article_url(pdf_url)
    elif "biorxiv.org" in pdf_url:
        referer = get_biorxiv_article_url(pdf_url)
    elif "arxiv.org" in pdf_url:
        referer = get_arxiv_article_url(pdf_url)

    if referer: headers["Referer"] = referer

    domain = get_domain_from_url(pdf_url)
    cookies = load_cookies()
    cookie_header = cookies.get(domain, "")
    if cookie_header:
        headers["Cookie"] = cookie_header

    try:
        r = requests.get(pdf_url, headers=headers, timeout=30, allow_redirects=True)
        if r.status_code == 403 or (b"Just a moment..." in r.content):
            print(f"PDF download forbidden or Cloudflare detected: {pdf_url}")
            ## Change: Simplified to one non-headless call
            print("Trying Selenium...")
            success, fail_reason = download_pdf_selenium(pdf_url, filename)
            return success, fail_reason if not success else None

        r.raise_for_status()
        with open(filename, "wb") as f:
            f.write(r.content)
        return True, None
    except Exception as e:
        print(f"Failed to download PDF from {pdf_url}: {e}")
        ## Change: Simplified to one non-headless call
        print("Trying Selenium as fallback...")
        success, fail_reason = download_pdf_selenium(pdf_url, filename)
        if success:
            return True, None
        else:
            return False, str(e) + f" | Selenium: {fail_reason}"


def load_download_log_dict(log_path="download_log.json"):
    if os.path.exists(log_path):
        try:
            with open(log_path, "r") as f:
                log_list = json.load(f)
                return {(entry.get("doi") or entry.get("title")): entry for entry in log_list}
        except Exception:
            return {}
    return {}


def save_download_log_dict(log_dict, log_path="download_log.json"):
    with open(log_path, "w") as f:
        json.dump(list(log_dict.values()), f, indent=2)


def scrape_pdf_with_selenium(url, filename=None):
    chrome_options = uc.ChromeOptions()
    ## Change: Respects the global RUN_HEADLESS setting
    if RUN_HEADLESS:
        chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument(
        f'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36')

    driver = None
    try:
        driver = uc.Chrome(options=chrome_options, version_main=138, browser_executable_path='/usr/bin/google-chrome')

        _load_cookies_into_driver(driver, url)

        print("Selenium browser started.")
        driver.get(url)
        pytime.sleep(5)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        pytime.sleep(2)

        wait = WebDriverWait(driver, 10)
        selectors = [
            (By.XPATH,
             "//a[contains(@href, '.pdf') or contains(text(), 'PDF') or contains(@aria-label, 'PDF') or contains(@data-testid, 'pdf-download-link') or contains(@class, 'pdf-link') or contains(@title, 'PDF')]"),
            (By.CSS_SELECTOR, "a[href$='.pdf']"),
        ]

        for by, sel in selectors:
            try:
                elem = wait.until(EC.element_to_be_clickable((by, sel)))
                href = elem.get_attribute("href")
                if href and ".pdf" in href:
                    driver.quit()
                    return href
            except Exception:
                continue

        print(f"PDF button not found on {url}. May be paywalled or unavailable.")
        if filename:
            with open(filename + '.debug.html', 'w', encoding='utf-8') as f:
                f.write(driver.page_source)

        driver.quit()
        return None
    except Exception as e:
        print(f"Selenium scraping error: {e}")
        if driver:
            driver.quit()
        return None


def main():
    with open(INPUT_JSON, "r") as f:
        data = json.load(f)
    citing_articles = data.get("citing_articles", [])
    log_dict = load_download_log_dict()
    for idx, article in enumerate(citing_articles):
        title = article.get("title")
        authors = article.get("authors")
        semantic_url = article.get("url")
        pub_url = article.get("pub_url")
        doi = article.get("doi") or get_doi_from_crossref(title, authors)
        print(f"[{idx + 1}/{len(citing_articles)}] Processing: {title}")
        log_key = doi or title
        if log_dict.get(log_key, {}).get("downloaded", False):
            print(f"  Already downloaded. Skipping.")
            continue

        pdf_url = None
        if doi: pdf_url = get_pdf_link_from_unpaywall(doi)
        if not pdf_url and semantic_url: pdf_url = get_pdf_link_from_semanticscholar(semantic_url)
        if not pdf_url: pdf_url = get_pdf_link_from_arxiv_biorxiv(article)
        if not pdf_url and doi: pdf_url = get_pdf_link_from_publisher_page(doi)
        if not pdf_url and pub_url:
            print(f"Trying public link: {pub_url}")
            pdf_url = scrape_pdf_with_selenium(pub_url, filename=title[:50])

        if pdf_url and isinstance(pdf_url, str) and pdf_url.startswith("http"):
            safe_title = "_".join(title.split())[:100]
            filename = os.path.join(PDF_DIR, f"{safe_title}.pdf")
            success, fail_reason = download_pdf(pdf_url, filename)
            log_entry = {"title": title, "doi": doi, "pdf_url": pdf_url, "downloaded": success,
                         "fail_reason": fail_reason}
            print(f"  PDF {'downloaded' if success else 'failed'}: {pdf_url}")
        else:
            reason = "No PDF found (may be paywalled or unavailable)"
            log_entry = {"title": title, "doi": doi, "pdf_url": None, "downloaded": False, "fail_reason": reason}
            print(f"  No PDF found. Reason: {reason}")

        log_dict[log_key] = log_entry
        save_download_log_dict(log_dict)
        time.sleep(1)

    print("\nDone. Log saved to download_log.json.")


if __name__ == "__main__":
    main()