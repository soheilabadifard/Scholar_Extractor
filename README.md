# Scholarly Citation Extractor

A command-line tool to extract citation information for academic papers from Google Scholar and Semantic Scholar.

## Overview

This tool allows you to search for an academic paper by title (and optionally author/year) and retrieve information about articles that have cited it. It can use either Google Scholar, Semantic Scholar, or both as data sources.

## Features

- **Multiple Data Sources**: Can use Google Scholar, Semantic Scholar, or both
- **Automatic Fallback**: If Google Scholar access is blocked, automatically falls back to Semantic Scholar
- **Detailed Citation Information**: Retrieves titles, authors, publication years, and more
- **Proxy Support**: Optional proxy support for Google Scholar to help bypass access restrictions
- **Rate Limiting Handling**: Automatic retry with exponential backoff for Semantic Scholar API rate limits
- **Configurable**: Adjustable timeouts, delays, retries, and result limits

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/Scholar_Extractor.git
   cd Scholar_Extractor
   ```

2. Install the required dependencies:
   ```
   pip install scholarly requests
   ```

## Usage

Basic usage:

```
python main.py "Title of the paper"
```

### Command-line Options

| Option | Description |
|--------|-------------|
| `title` | Title of the article to search for (required) |
| `-a, --author` | Author name to refine the search |
| `-y, --year` | Publication year to refine the search |
| `-m, --max-results` | Maximum number of citing articles to retrieve (default: 100) |
| `-o, --output` | Output file name (default: citations_<scholar_id>.json) |
| `-t, --timeout` | Timeout in seconds for operations (default: 30) |
| `-p, --use-proxy` | Use free proxies for requests (Google Scholar only) |
| `-d, --delay` | Min and max delay between requests in seconds (default: 1 3) |
| `-s, --source` | Data source to use: google, semantic, or both (default: both) |
| `-r, --retries` | Maximum number of retry attempts for rate-limited requests (default: 3) |

### Examples

Search for a paper by title and author, using both data sources:
```
python main.py "Machine Learning: A Probabilistic Perspective" -a "Murphy"
```

Search using only Semantic Scholar (useful if Google Scholar is blocking your requests):
```
python main.py "Deep Learning" -a "Goodfellow" -s semantic
```

Increase timeout and delay to avoid being blocked:
```
python main.py "Attention Is All You Need" -t 60 -d 3 5
```

Increase retry attempts for Semantic Scholar API rate limiting:
```
python main.py "Attention Is All You Need" -s semantic -r 5
```

## Data Sources

### Google Scholar
- Pros: Comprehensive coverage across many fields
- Cons: Actively blocks scraping attempts, may require proxy

### Semantic Scholar
- Pros: Provides a stable API, less likely to be blocked
- Cons: May have less comprehensive coverage in some fields

## Troubleshooting

If you encounter issues with Google Scholar blocking your requests:

1. Try using the `--source=semantic` option to use only Semantic Scholar
2. Try using the `--use-proxy` option to route Google Scholar requests through a proxy
3. Increase the delay between requests with `-d 3 5` or higher values
4. Try again later when Google Scholar may have reset your IP status

If you encounter rate limiting issues with Semantic Scholar API:

1. Increase the number of retry attempts with `-r 5` or higher
2. Increase the delay between requests with `-d 3 5` or higher values
3. Set up a Semantic Scholar API key (strongly recommended):
   - Register for a free API key at https://www.semanticscholar.org/product/api
   - Set the API key as an environment variable:
     ```
     # Linux/macOS
     export SEMANTIC_SCHOLAR_API_KEY="your_api_key_here"
     
     # Windows (Command Prompt)
     set SEMANTIC_SCHOLAR_API_KEY=your_api_key_here
     
     # Windows (PowerShell)
     $env:SEMANTIC_SCHOLAR_API_KEY="your_api_key_here"
     ```
   - For persistent use, add the export/set command to your shell profile

## Output Format

The script outputs a JSON file with the following structure:

```
{
  "input_article": {
    "title": "Paper Title",
    "authors": "Author Names",
    "year": "Publication Year",
    "venue": "Publication Venue",
    "abstract": "Paper Abstract",
    "url": "URL to Paper",
    "citations_count": 42,
    "scholar_id": "Scholar ID"
  },
  "citing_articles": [
    {
      "title": "Citing Paper Title",
      "authors": "Citing Authors",
      "year": "Citation Year",
      "venue": "Citation Venue",
      "abstract": "Citation Abstract",
      "url": "URL to Citation",
      "citations_count": 10,
      "scholar_id": "Citation ID"
    }
    /* Additional citing articles would be listed here */
  ],
  "total_citations_found": 42,
  "total_citations_available": 100,
  "data_source": "google_scholar"  /* or "semantic_scholar" */
}
```

The `data_source` field will contain either "google_scholar" or "semantic_scholar" depending on which source was used to retrieve the data.

## Limitations

- Google Scholar actively blocks automated scraping attempts
- Running this script too frequently may result in your IP being temporarily blocked by Google
- This script is intended for educational and research purposes only

## License

This project is licensed under the MIT License - see the LICENSE file for details.