import os
import random
import re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from seleniumbase import Driver

from bs4 import BeautifulSoup
from dotenv import load_dotenv
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse, quote
from output_writer import save_to_json, save_to_csv

import argparse
from input_handler import read_urls_from_file


# Load .env from root directory
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path)




def get_clutch_search_results(search_query, headless=True):
    """
    Performs a search on clutch.co and gets top 2 list of companies pages.

    Args:
        search_query (str): The query to pass on https://clutch.co/search.

    Returns:
        list: List of HTML contents of company profile pages from https://clutch.co/profile.
    """
    BASE_URL = "https://clutch.co"
    search_url = f"{BASE_URL}/search?q={quote(search_query)}"

    try:
        # service = Service()
        # driver = webdriver.Chrome(service=service, options=options)

        driver = Driver(uc=True, headless=headless)

    except Exception as e:
        print(f"[❌] Error setting up Selenium WebDriver: {e}")
        return []

    print(f"[🔍] Searching for: {search_query} on {search_url}...")
    html_pages = []

    try:
        driver.uc_open_with_reconnect(search_url, reconnect_time=2)

        # Wait for search results
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "companies-results"))
        )

        # Find top 2 company list links
        company_list_links = driver.find_elements(By.CSS_SELECTOR, "#companies-results a.companies_item")
        target_urls = [urljoin(BASE_URL, link.get_attribute("href")) for link in company_list_links[:2]]

        for i, target_url in enumerate(target_urls):
            try:
                # target_url = urljoin(BASE_URL, link.get_attribute("href"))
                print(f"Navigating to company list {i+1}: {target_url}")

                driver.uc_open_with_reconnect(target_url, 3)
                driver.uc_gui_click_captcha()

                try:
                    # Wait for company listings to load
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "section#providers__section, ul#providers__list"))
                    )
                except:
                    print(f"No Company listings found on {target_url}, skipping this page...")
                    continue

                company_profile_link_elements = driver.find_elements(By.CSS_SELECTOR , "a.provider__title-link")
                if not company_profile_link_elements:
                    print(f"No company profiles found on {target_url}")
                    continue

                company_profile_links = [urljoin(BASE_URL, link.get_attribute("href")) for link in company_profile_link_elements]

                # Fetch profile pages in parallel using requests
                with ThreadPoolExecutor() as executor:
                    profile_pages = list(executor.map(fetch_profile_page, company_profile_links))

                # Add valid pages to html_pages
                for page_content in profile_pages:
                    if page_content:
                        html_pages.append(page_content)

            except Exception as e:
                print(f"Error processing company list {i+1}: {e}")
                continue

        return html_pages

    except Exception as e:
        print(f"Error during search: {e}")
        return []
    finally:
        if 'driver' in locals() and driver:
            driver.quit()


def fetch_profile_page(profile_link):
    """Fetch a single profile page using requests"""
    try:
        response = requests.get(
            profile_link,
            timeout=10,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        return response.text
    except Exception as e:
        print(f"Error fetching company profile of {profile_link}: {e}")
        return None


def parse_clutch_results(html_pages):
    """
    Parses HTML pages from clutch.co to extract company data.

    Args:
        html_pages (list): List of HTML content from company list pages.

    Returns:
        list: Combined list of company dictionaries.
    """
    all_companies = []
    redirect_urls = []

    for i, html_content in enumerate(html_pages):
        if not html_content:
            continue

        company = BeautifulSoup(html_content, 'html.parser')
        print("Company:", company)

        try:
            # Extract Company Name
            name_element = company.find('h1', class_='profile-header__title', attrs={'itemprop': "name"})

            if name_element:
                company_name = name_element.get_text(strip=True)
                # Normalize Unicode characters
                company_name = unicodedata.normalize('NFKC', company_name)
            else:
                company_name = None

            # Get website link from redirect URL
            website_link_element = company.find('a', class_='website-link__item', href=True)
            redirect_url = website_link_element.get('href') if website_link_element else None

            details_section = company.find('ul', class_='profile-summary__details')
            location = None
            founded_year = None

            if details_section:
                detail_items = details_section.find_all('li', class_='profile-summary__detail')

                for item in detail_items:
                    label = item.find('span', class_='profile-summary__detail-label')
                    value = item.find('span', class_='profile-summary__detail-title')

                    if not label or not value:
                        continue

                    label_text = label.get_text(strip=True).lower()
                    value_text = value.get_text(strip=True)

                    if 'location' in label_text:
                        location = value_text
                    elif 'founded' in label_text:
                        # Extract the year from something like "Founded 1996"
                        match = re.search(r'\b(19|20)\d{2}\b', value_text)
                        founded_year = match.group(0) if match else value_text

            services = []

            # Locate the service pie chart section
            services_list = company.find_all('li', class_='chart-legend--item')

            for service_item in services_list:
                try:
                    service_name_tag = service_item.find('h3')
                    service_name = service_name_tag.get_text(strip=True) if service_name_tag else None

                    percentage_tag = service_item.find('span')
                    percentage = percentage_tag.get_text(strip=True) if percentage_tag else None

                    if service_name and percentage:
                        services.append(f"{service_name} ({percentage})")
                except Exception as e:
                    print(f"[⚠️] Error extracting service: {e}")
                    continue

            all_companies.append({
                'Company Name': company_name,
                'Website URL': None,
                'Location': location,
                'Services': services,
                'Founded Year': founded_year
            })
            redirect_urls.append(redirect_url)
        except Exception as e:
            print(f"Error parsing company data: {e}")
            continue

    # Resolve URLs in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        actual_company_urls = list(executor.map(get_final_website_url, redirect_urls))

    # Update company data with resolved URLs
    for i, actual_company_url in enumerate(actual_company_urls):
        if i < len(all_companies):
            all_companies[i]['Website URL'] = actual_company_url

    return all_companies


def get_final_website_url(redirect_url):
    """
    Attempts to get the final URL after following redirects using requests.

    Args:
        redirect_url (str): The initial URL that might redirect.

    Returns:
        str: The final URL after redirects, or None if an error occurs.
    """
    if not redirect_url:
        return None

    request_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        response = requests.get(
            redirect_url,
            allow_redirects=True,
            timeout=5,
            verify=False,  # Skip SSL verification
            headers=request_headers
        )
        parsed = urlparse(response.url)
        return f"{parsed.scheme}://{parsed.netloc}"

    except requests.exceptions.RequestException as e:
        print(f"[❌] Error resolving final URL for {redirect_url}: {e}")
        return None


def remove_duplicates(companies):
    """Remove duplicate companies based on company name or website URL."""
    seen = set()
    unique_companies = []

    for company in companies:
        name = company.get('Company Name', '').strip().lower() if company.get('Company Name') else ''
        url = company.get('Website URL', '').strip().lower() if company.get('Website URL') else ''

        # Create identifier (use name or URL, whichever is available)
        identifier = name or url

        if identifier and identifier not in seen:
            seen.add(identifier)
            unique_companies.append(company)

    return unique_companies


def main():
    parser = argparse.ArgumentParser(description="Company Scraper Tool")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--url-file', type=str, help='Path to file containing seed URLs')
    group.add_argument('--query', type=str, help='Search query for discovering companies')
    parser.add_argument('--output', '-o', choices=['json', 'csv'], default='csv',
                        help='Output format: json or csv (default)')

    args = parser.parse_args()

    company_data = []

    if args.url_file:
        print(f"📥 Reading URLs from: {args.url_file}")
        urls = read_urls_from_file(args.url_file)
        print(f"[!] Direct URL scraping not implemented yet. Found {len(urls)} URLs.")
        # TODO: Implement direct company website scraping

    elif args.query:
        print(f"🔍 Searching for: '{args.query}'")
        html_pages = get_clutch_search_results(args.query, headless=False)

        if html_pages:
            company_data = parse_clutch_results(html_pages)

            if company_data:
                # Remove duplicates
                unique_companies = remove_duplicates(company_data)
                print(f"Extracted {len(company_data)} companies, {len(unique_companies)} unique")
                company_data = unique_companies
            else:
                print("Could not extract any company data.")
        else:
            print("No pages retrieved.")

    else:
        print("Provide either --url-file or --query")
        return

    if company_data:
        # Convert list of services to a joined string for CSV
        if args.output == 'csv':
            for company in company_data:
                if 'Services' in company and isinstance(company['Services'], list):
                    company['Services'] = '; '.join(company['Services'])  # Convert list to string for CSV

        if args.output == 'json':
            save_to_json(company_data)
        else:
            save_to_csv(company_data)
    else:
        print("No company data extracted.")


if __name__ == "__main__":
    main()
