# Robust Web Scraping Service

A production-grade web scraping service built with FastAPI and Playwright for extracting news, blog, and article content from competitor websites.

## Features

🟢 **Robust Scraping**: Uses Playwright for full JavaScript rendering and content extraction
🟢 **Smart Content Loading**: Automatically scrolls and clicks "Load More" buttons
🟢 **Retry Logic**: Built-in retry mechanisms with exponential backoff
🟢 **Rate Limiting**: Randomized delays between requests to avoid blocks
🟢 **Authentication**: Token-based security for API endpoints
🟢 **Production Ready**: Deployable on Render with proper error handling and logging

## Quick Start

### Local Development

1. **Install dependencies**:
```bash
pip install -r requirements.txt
playwright install chromium
playwright install-deps
```

2. **Set environment variables** (optional):
```bash
export PORT=8000
```

3. **Run the service**:
```bash
python main.py
```

The service will be available at `http://localhost:8000`

### Docker Deployment

```bash
docker build -t robust-scraping-service .
docker run -p 8000:8000 robust-scraping-service
```

### Render Deployment

1. Connect your GitHub repository to Render
2. Render will automatically detect the `render.yaml` configuration
3. The service will be deployed with all necessary dependencies

## API Usage

The API is now open and doesn't require authentication for simplicity.

### Scrape Websites

**Endpoint**: `POST /scrape`

**Headers**:
```
Content-Type: application/json
```

**Request Body**:
```json
{
  "base_urls": [
    "https://www.variotherm.com/en/service/news/projects-of-the-month.html",
    "https://another-company.com/blog"
  ],
  "max_articles_per_url": 50,
  "delay_range": [2, 5]
}
```

**Response**:
```json
{
  "success": true,
  "message": "Successfully scraped 2 URLs, found 15 articles",
  "data": {
    "scrapeResult1": {
      "base_url": "https://www.variotherm.com/en/service/news/projects-of-the-month.html",
      "articles": [
        {
          "title": "Article Title",
          "date": "2024-01-15",
          "content": "Full article content...",
          "image": "https://example.com/image.jpg",
          "url": "https://example.com/article"
        }
      ],
      "total_articles_found": 8,
      "successfully_processed": 8
    },
    "scrapeResult2": {
      "base_url": "https://another-company.com/blog",
      "articles": [...],
      "total_articles_found": 7,
      "successfully_processed": 7
    }
  },
  "timestamp": "2024-01-15T10:30:00",
  "total_urls_processed": 2,
  "total_articles_found": 15
}
```

### Health Check

**Endpoint**: `GET /health`

Returns service status and version information.

## Configuration

### Environment Variables

- `PORT`: Port number for the service (default: 8000)
- `PYTHON_VERSION`: Python version (default: 3.11.0)

### Scraping Parameters

- `max_articles_per_url`: Maximum number of articles to extract per URL (default: 50)
- `delay_range`: Range of random delays between requests in seconds (default: [2, 5])

## Features in Detail

### Smart Content Loading

The service automatically:
- Scrolls to the bottom of pages
- Clicks "Load More", "Show More", and pagination buttons
- Waits for lazy-loaded content to appear
- Detects when all content has been loaded

### Robust Error Handling

- Retry logic with exponential backoff
- Graceful handling of network timeouts
- Detailed error logging
- Fallback mechanisms for content extraction

### Anti-Detection Measures

- Rotating user agents
- Randomized delays between requests
- Custom headers to mimic real browsers
- Resource blocking for faster scraping

### Content Extraction

Extracts the following from each article:
- **Title**: From H1 tags, meta tags, or article titles
- **Publication Date**: From meta tags, time elements, or URL patterns
- **Content**: Full article text with proper formatting
- **Images**: Featured images, OpenGraph images, or article images
- **URL**: Original article URL

## Logging

The service provides comprehensive logging:
- Request/response logging
- Error tracking with stack traces
- Performance metrics
- Failed URL tracking

Logs are written to both console and `scraper.log` file.

## Security

- Input validation with Pydantic models
- CORS configuration for web access
- Environment variable management

## Performance

- Asynchronous processing for better throughput
- Resource optimization (blocks unnecessary assets)
- Memory-efficient content extraction
- Configurable rate limiting

## Troubleshooting

### Common Issues

1. **Playwright Installation**: Ensure you run `playwright install chromium` and `playwright install-deps`
2. **Memory Issues**: Reduce `max_articles_per_url` for large sites
3. **Timeout Errors**: Increase delays in `delay_range`
4. **Network Issues**: Check if the target websites are accessible

### Debug Mode

Enable debug logging by setting the log level:
```python
logging.getLogger().setLevel(logging.DEBUG)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs for error details
3. Open an issue on GitHub with detailed information
