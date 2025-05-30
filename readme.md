# Driply Webscraping

A Python web scraper for extracting product images and metadata from Farfetch, uploading images to Google Cloud Storage, and storing metadata in Firestore.

## Features

- Scrapes product images, brand names, and product descriptions from Farfetch listings.
- Downloads images and uploads them to a specified Google Cloud Storage bucket.
- Stores product metadata in a Firestore collection.
- Keeps track of already-uploaded images to avoid duplicates.
- Exposes a REST API endpoint for scraping via Flask.

## Requirements

- Python 3.8+
- Google Cloud credentials (for Storage and Firestore)
- [Playwright](https://playwright.dev/python/)
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/)
- [Flask](https://flask.palletsprojects.com/)
- [Rich](https://rich.readthedocs.io/)
- [requests](https://docs.python-requests.org/)

Install dependencies:

```sh
pip install -r requirements.txt
```

## Usage

### 1. Start the server

```sh
python main.py
```

The server will run on `http://127.0.0.1:8080`.

### 2. Make a scrape request

Use `curl` or any HTTP client to POST to `/scrape`:

```sh
curl -X POST http://localhost:8080/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "url": -URL-,
    "firestore_collection": "wardrobe",
    "max_items": 3
  }'
```

#### Request Parameters

- `url` (string, required): Farfetch listing URL to scrape.
- `bucket_name` (string, required): Google Cloud Storage bucket name.
- `firestore_collection` (string, required): Firestore collection for metadata.
- `max_items` (int, optional): Maximum number of products to process.

#### Response

Returns a JSON object with the number of successful and failed uploads, and the Firestore document IDs.

```json
{
  "uploaded": 3,
  "failed": 0,
  "firestore_docs": [
    "docid1",
    "docid2",
    "docid3"
  ]
}
```

## Project Structure

- [`main.py`](main.py): Main application and API server.
- [`uploaded_links.json`](uploaded_links.json): Tracks already-uploaded image URLs.
- [`requirements.txt`](requirements.txt): Python dependencies.
- [`readme.md`](readme.md): Project documentation.

## Notes

- Playwright requires browser binaries. Install them with:
  ```sh
  playwright install
  ```
- This project is intended for educational and personal use. Respect the terms of service of any website you scrape.