#!/usr/bin/env python3
"""
Academic Citation Extractor for Semantic Scholar and SerpApi (Google Scholar)

This script takes an article title as input and retrieves information about
articles that have cited it, using the Semantic Scholar and/or SerpApi.

FEATURES:
- Dual API support for comprehensive citation data.
- Combines and deduplicates results from both sources based on title.
- Enriches data by merging unique details from each source.
- Handles API errors and pagination for both platforms.

REQUIREMENTS:
- API keys are recommended for Semantic Scholar and required for SerpApi.
- Set keys as environment variables: 'SEMANTIC_SCHOLAR_API_KEY' and 'SERPAPI_API_KEY'.
"""

import sys
import os
import json
import time
import argparse
import requests
from typing import Dict, List, Optional
from dotenv import load_dotenv


# --- Helper Functions ---
def normalize_title(title: str) -> str:
    """A simple function to normalize titles for comparison."""
    if not title: return ""
    return ''.join(char.lower() for char in title if char.isalnum())


def format_article_info(article: Dict) -> Dict:
    """Formats the article dictionary into a clean, final structure."""
    return {
        'title': article.get('bib', {}).get('title'),
        'authors': article.get('bib', {}).get('author'),
        'year': article.get('bib', {}).get('pub_year'),
        'venue': article.get('bib', {}).get('venue'),
        'abstract': article.get('bib', {}).get('abstract'),
        'pub_url': article.get('pub_url'),
        'doi': article.get('doi'),
        'citations_count_semantic': article.get('num_citations_semantic'),
        'citations_count_google': article.get('num_citations_google'),
        'semantic_scholar_id': article.get('semantic_scholar_id'),
        'google_scholar_cites_id': article.get('google_scholar_cites_id'),
        'data_sources': article.get('data_sources', [])
    }


def handle_http_error(e: requests.exceptions.HTTPError, source: str):
    """Provides specific feedback for different HTTP status codes."""
    status_code = e.response.status_code
    if status_code in [401, 403]:
        print(f"Error: [{source}] Access denied (401/403). Please ensure your API key is correct and valid.")
    elif status_code == 404:
        print(f"Error: [{source}] The requested resource was not found (404).")
    elif status_code >= 500:
        print(f"Error: [{source}] A server-side error occurred ({status_code}). Please try again later.")
    else:
        print(f"An unexpected HTTP error occurred [{source}]: {e}")


# --- Semantic Scholar Functions ---
def search_semantic_scholar(api_key: str, title: str, **kwargs) -> Optional[Dict]:
    """Searches for an article on Semantic Scholar."""
    print(f"Searching Semantic Scholar for: {title}")
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {"query": title, "limit": 1, "fields": "title,authors,year,venue,abstract,url,citationCount,externalIds"}
    headers = {'x-api-key': api_key} if api_key else {}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=kwargs.get('timeout', 30))
        response.raise_for_status()
        data = response.json()
        papers = data.get('data', [])
        if not papers:
            print("Article not found on Semantic Scholar.")
            return None
        paper = papers[0]
        print("Article found on Semantic Scholar.")
        return {
            'bib': {
                'title': paper.get('title'),
                'author': ', '.join([a.get('name', '') for a in paper.get('authors', [])]),
                'pub_year': paper.get('year'),
                'venue': paper.get('venue'),
                'abstract': paper.get('abstract')
            },
            'pub_url': paper.get('url'),
            'num_citations_semantic': paper.get('citationCount', 0),
            'semantic_scholar_id': paper.get('paperId', ''),
            'doi': paper.get('externalIds', {}).get('DOI')
        }
    except requests.exceptions.HTTPError as e:
        handle_http_error(e, "Semantic Scholar Search")
        return None
    except requests.exceptions.RequestException as e:
        print(f"A network error occurred during Semantic Scholar search: {e}")
        return None


def get_semantic_scholar_citations(api_key: str, article: Dict, max_results: int, **kwargs) -> List[Dict]:
    """Gets citations from Semantic Scholar."""
    paper_id = article.get('semantic_scholar_id')
    if not paper_id: return []
    print(f"\nRetrieving Semantic Scholar citations for: {article['bib']['title']}")
    citing_articles, offset, limit = [], 0, 100
    url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}/citations"
    headers = {'x-api-key': api_key} if api_key else {}
    while len(citing_articles) < max_results:
        params = {"offset": offset, "limit": min(limit, max_results - len(citing_articles)),
                  "fields": "title,authors,year,venue,abstract,url,citationCount,externalIds"}
        try:
            response = requests.get(url, params=params, headers=headers, timeout=kwargs.get('timeout', 30))
            response.raise_for_status()
            data = response.json()
            citations_data = data.get('data', [])
            if not citations_data: break
            for item in citations_data:
                paper = item.get('citingPaper', {})
                citing_articles.append({
                    'bib': {'title': paper.get('title'),
                            'author': ', '.join([a.get('name', '') for a in paper.get('authors', [])]),
                            'pub_year': paper.get('year'), 'venue': paper.get('venue')},
                    'pub_url': paper.get('url'), 'num_citations': paper.get('citationCount', 0),
                    'semantic_scholar_id': paper.get('paperId'), 'doi': paper.get('externalIds', {}).get('DOI')
                })
            print(f"Retrieved {len(citing_articles)} Semantic Scholar citations...", end="\r")
            if 'next' in data and data['next']:
                offset = data['next']
                time.sleep(0.3)
            else:
                break
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                print("Rate limit hit on Semantic Scholar citations. Waiting 10 seconds...")
                time.sleep(10)
                continue
            handle_http_error(e, "Semantic Scholar Citations")
            break
        except requests.exceptions.RequestException as e:
            print(f"A network error occurred retrieving Semantic Scholar citations: {e}")
            break
    print(f"\nFinished retrieving {len(citing_articles)} citations from Semantic Scholar.")
    return citing_articles


# --- SerpApi Google Scholar Functions ---
def search_serpapi_google_scholar(api_key: str, title: str, **kwargs) -> Optional[Dict]:
    """Searches for an article on Google Scholar via SerpApi."""
    print(f"Searching Google Scholar (via SerpApi) for: {title}")
    params = {
        "engine": "google_scholar",
        "q": title,
        "api_key": api_key
    }
    try:
        response = requests.get("https://serpapi.com/search", params=params, timeout=kwargs.get('timeout', 30))
        response.raise_for_status()
        data = response.json()
        results = data.get('organic_results', [])
        if not results:
            print("Article not found via SerpApi.")
            return None
        top_result = results[0]
        pub_info = top_result.get('publication_info', {})
        cited_by = top_result.get('inline_links', {}).get('cited_by', {})
        print("Article found via SerpApi.")
        return {
            'bib': {'title': top_result.get('title'), 'author': pub_info.get('summary'),
                    'pub_year': next((part for part in pub_info.get('summary', '').split(' - ')[0] if
                                      part.isdigit() and len(part) == 4), None),
                    'venue': pub_info.get('summary', '').split(' - ')[-1], 'abstract': top_result.get('snippet')
                    },
            'pub_url': top_result.get('link'), 'num_citations_google': cited_by.get('total', 0),
            'google_scholar_cites_id': cited_by.get('cites_id')
        }
    except requests.exceptions.HTTPError as e:
        handle_http_error(e, "SerpApi Search")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error searching SerpApi: {e}")
        return None


def get_serpapi_citations(api_key: str, article: Dict, max_results: int, **kwargs) -> List[Dict]:
    """Gets citations from Google Scholar via SerpApi."""
    cites_id = article.get('google_scholar_cites_id')
    if not cites_id: return []
    print(f"\nRetrieving Google Scholar citations for: {article['bib']['title']}")
    citing_articles, start = [], 0
    while len(citing_articles) < max_results:
        params = {"engine": "google_scholar", "cites": cites_id, "start": start, "num": 20, "api_key": api_key}
        try:
            response = requests.get("https://serpapi.com/search", params=params, timeout=kwargs.get('timeout', 30))
            response.raise_for_status()
            data = response.json()
            results = data.get('organic_results', [])
            if not results: break
            for result in results:
                pub_info = result.get('publication_info', {})
                cited_by = result.get('inline_links', {}).get('cited_by', {})
                citing_articles.append({
                    'bib': {'title': result.get('title'), 'author': pub_info.get('summary'),
                            'pub_year': next((part for part in pub_info.get('summary', '').split(' - ')[0] if
                                              part.isdigit() and len(part) == 4), None),
                            'venue': pub_info.get('summary', '').split(' - ')[-1]
                            }, 'pub_url': result.get('link'), 'num_citations_google': cited_by.get('total', 0),
                    'google_scholar_cites_id': cited_by.get('cites_id')
                })
            print(f"Retrieved {len(citing_articles)} Google Scholar citations...", end="\r")
            if "next" in data.get("serpapi_pagination", {}):
                start += 20
                time.sleep(1)  # Politeness delay for subsequent pages
            else:
                break
        except requests.exceptions.HTTPError as e:
            handle_http_error(e, "SerpApi Citations")
            break
        except requests.exceptions.RequestException as e:
            print(f"\nError retrieving SerpApi citations: {e}")
            break
    print(f"\nFinished retrieving {len(citing_articles)} citations from Google Scholar.")
    return citing_articles


# --- Combination Logic ---
def combine_and_deduplicate_results(semantic_list: List[Dict], serpapi_list: List[Dict]) -> List[Dict]:
    """Combines and deduplicates citation lists."""
    print("\nCombining and deduplicating results from all sources...")
    combined = {}
    for article in semantic_list:
        norm_title = normalize_title(article['bib']['title'])
        if not norm_title: continue
        article['data_sources'] = ['semantic_scholar']
        combined[norm_title] = article
    for article in serpapi_list:
        norm_title = normalize_title(article['bib']['title'])
        if not norm_title: continue
        if norm_title in combined:
            combined[norm_title]['data_sources'].append('google_scholar_serpapi')
            for key, value in article.items():
                if key not in combined[norm_title] or not combined[norm_title][key]:
                    combined[norm_title][key] = value
        else:
            article['data_sources'] = ['google_scholar_serpapi']
            combined[norm_title] = article
    print(f"Total unique citations found: {len(combined)}")
    return list(combined.values())


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Academic Citation Extractor",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("title", type=str, help="Title of the article to search for.")
    parser.add_argument("-a", "--author", type=str, help="Author name to refine the search.")
    parser.add_argument("-s", "--source", type=str, choices=["semantic", "serpapi", "both"], default="both",
                        help="Data source(s) to use.")
    parser.add_argument("-m", "--max-results", type=int, default=1000,
                        help="Maximum number of citing articles to retrieve per source.")
    parser.add_argument("-o", "--output", type=str, help="Output JSON file name.")
    parser.add_argument("-t", "--timeout", type=int, default=30, help="Timeout in seconds for API requests.")
    return parser.parse_args()


def main():
    """Main function to run the script."""
    load_dotenv()
    args = parse_arguments()
    s_api_key = os.environ.get('SEMANTIC_SCHOLAR_API_KEY')
    serpapi_api_key = os.environ.get('SERPAPI_API_KEY')

    if args.source in ["serpapi", "both"] and not serpapi_api_key:
        print("Error: --source 'serpapi' or 'both' requires a SERPAPI_API_KEY environment variable.", file=sys.stderr)
        sys.exit(1)

    print("\n=== Academic Citation Extractor ===\n")
    input_article_semantic, input_article_serpapi = None, None
    citations_semantic, citations_serpapi = [], []
    search_params = {'title': args.title, 'author': args.author, 'timeout': args.timeout}

    if args.source in ["semantic", "both"]:
        input_article_semantic = search_semantic_scholar(s_api_key, **search_params)
        if input_article_semantic:
            citations_semantic = get_semantic_scholar_citations(s_api_key, input_article_semantic, args.max_results,
                                                                **search_params)

    if args.source in ["serpapi", "both"]:
        input_article_serpapi = search_serpapi_google_scholar(serpapi_api_key, **search_params)
        if input_article_serpapi:
            citations_serpapi = get_serpapi_citations(serpapi_api_key, input_article_serpapi, args.max_results,
                                                      **search_params)

    if not input_article_semantic and not input_article_serpapi:
        print("\nArticle could not be found in any specified source.")
        return

    final_input_article = (input_article_semantic or input_article_serpapi).copy()
    if input_article_semantic and input_article_serpapi:
        final_input_article = input_article_serpapi.copy()
        final_input_article.update(input_article_semantic)
        final_input_article['data_sources'] = ['semantic_scholar', 'google_scholar_serpapi']
    elif input_article_semantic:
        final_input_article['data_sources'] = ['semantic_scholar']
    else:
        final_input_article['data_sources'] = ['google_scholar_serpapi']

    final_citations = combine_and_deduplicate_results(citations_semantic, citations_serpapi)

    result = {
        'input_article': format_article_info(final_input_article),
        'citing_articles': [format_article_info(c) for c in final_citations],
        'total_citations_found': len(final_citations)
    }
    output_file = args.output or f"citations_{normalize_title(args.title)[:50]}.json"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to {output_file}")
    except IOError as e:
        print(f"\nError saving results to file: {e}")

    print("\n=== Extraction Complete ===\n")


if __name__ == '__main__':
    main()