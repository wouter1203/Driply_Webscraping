import os
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import requests
from rich.progress import track
from functions_framework import http
from flask import jsonify, request, Flask
from google.cloud import storage
from google.cloud import firestore
import uuid
import json
import time

# Configure logging for Cloud Run
logging.basicConfig(level=logging.INFO)

# It's good practice to define the User-Agent globally or at the top of the function
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def download_image(img_url_tuple, max_retries=3):
    idx, img_url, folder_name = img_url_tuple
    for attempt in range(1, max_retries + 1):
        try:
            logging.debug(f"Downloading image {idx} (attempt {attempt}): {img_url}")
            img_data = requests.get(img_url, timeout=10).content
            img_path = os.path.join(folder_name, f"image_{idx}.jpg")
            with open(img_path, "wb") as f:
                f.write(img_data)
            logging.info(f"✅ Downloaded image {idx} successfully!")
            return True
        except Exception as e:
            logging.warning(f"Failed to download {img_url} (attempt {attempt}): {e}")
            if attempt == max_retries:
                logging.error(f"❌ Giving up on {img_url} after {max_retries} attempts.")
                return False

def upload_image_to_gcs(image_bytes, bucket_name, blob_name):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    # Generate a UUID token
    token = str(uuid.uuid4())
    # Set the token as metadata
    blob.metadata = {"firebaseStorageDownloadTokens": token}
    blob.upload_from_string(image_bytes, content_type="image/jpeg")
    blob.patch()  # Ensure metadata is saved

    # Construct the Firebase download URL
    url = (
        f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/"
        f"{requests.utils.quote(blob_name, safe='')}"
        f"?alt=media&token={token}"
    )
    return url

def scrape_listing_images(url, bucket_name, firestore_collection, max_items=None):
    logging.info(f"Starting scrape_listing_images for URL: {url}")

    total_start_time = time.time()

    uploaded_links = load_uploaded_links()
    new_uploaded_links = set(uploaded_links)

    # Create a session object
    with requests.Session() as session:
        # Set default headers for the session
        session.headers.update(HEADERS)

        with sync_playwright() as p:
            logging.debug("Launching browser...")
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            logging.debug("Navigating to page...")
            # It's good practice to also set a User-Agent for Playwright if you want consistency,
            # though it's the requests part we're primarily fixing for image downloads.
            # page.set_extra_http_headers({"User-Agent": HEADERS['User-Agent']}) # Optional for Playwright
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            logging.debug("Scrolling to load more products...")

            scroll_pause = 5
            last_height = page.evaluate("() => document.body.scrollHeight")
            for i in range(10):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                page.wait_for_timeout(int(scroll_pause * 1000))
                new_height = page.evaluate("() => document.body.scrollHeight")
                logging.debug(f"Scrolled to {new_height} (step {i+1})")
                if new_height == last_height:
                    logging.debug("No more content to load.")
                    break
                last_height = new_height

            logging.debug("Waiting for product images to load...")
            try:
                page.wait_for_selector('img.ltr-io0g65', timeout=10000)
                logging.debug("Product images loaded.")
            except Exception as e:
                logging.error(f"Timeout waiting for images: {e}")
                browser.close()
                return {"error": "Timeout waiting for images."}
            page_content = page.content()
            browser.close()
            logging.debug("Browser closed.")

        logging.debug("Parsing HTML with BeautifulSoup...")
        soup = BeautifulSoup(page_content, "html.parser")

        logging.debug("Searching for all <img> tags...")
        img_tags = soup.find_all("img")
        logging.debug(f"Found {len(img_tags)} <img> tags.")
        img_urls = []
        for img in img_tags:
            src = img.get("src")
            if (
                src
                and src.startswith("https://cdn-images.farfetch-contents.com/")
                and src.endswith(".jpg")
            ):
                img_urls.append(src)
                logging.debug(f"Added image URL: {src}")
                if max_items and len(img_urls) >= max_items:
                    break

        brands = [p.get_text(strip=True) for p in soup.find_all("p", {"data-component": "ProductCardBrandName"})]
        product_names = [p.get_text(strip=True) for p in soup.find_all("p", {"data-component": "ProductCardDescription"})]

        if max_items:
            brands = brands[:max_items]
            product_names = product_names[:max_items]

        if not img_urls:
            logging.warning("No product images found.")
            return {"error": "No product images found."}

        db = firestore.Client()
        successful_uploads = 0
        failed_uploads = 0
        uploaded_docs = []

        for img_url, brand, product in zip(img_urls, brands, product_names):
            iter_start_time = time.time()
            if img_url in uploaded_links:
                logging.info(f"Skipping already uploaded image with doc_id: [already_uploaded]")
                continue
            attempt = 0
            success = False
            while attempt < 3 and not success:
                attempt += 1
                try:
                    logging.info(f"Attempt {attempt} for image doc_id: [pending]")
                    img_download_start = time.time()
                    response = session.get(img_url, timeout=10, stream=True)
                    response.raise_for_status()
                    img_data = response.content
                    img_download_end = time.time()
                    # Create Firestore doc to get doc_id before upload
                    doc_ref = db.collection(firestore_collection).document()
                    doc_id = doc_ref.id
                    folder_prefix = "wardrobe"
                    blob_name = f"{folder_prefix}/{doc_id}.jpg"
                    logging.info(f"Downloading image for doc_id: {doc_id}")
                    gcs_upload_start = time.time()
                    public_url = upload_image_to_gcs(img_data, bucket_name, blob_name)
                    gcs_upload_end = time.time()
                    logging.info(f"GCS upload for doc_id: {doc_id} took {gcs_upload_end - gcs_upload_start:.2f} seconds")
                    metadata = {
                        "brand_name": brand,
                        "name": product,
                        "imageUrl": public_url,
                        "doc_id": doc_id,
                        "color": "unknown",
                        "pattern": "unknown",
                        "type": "Shirt",
                    }
                    doc_ref.set(metadata)
                    uploaded_docs.append(doc_id)
                    successful_uploads += 1
                    new_uploaded_links.add(img_url)
                    success = True
                except requests.exceptions.RequestException as e:
                    logging.error(f"Failed to download image for doc_id: {doc_id if 'doc_id' in locals() else '[unknown]'} (attempt {attempt}): {e}")
                    if attempt == 3:
                        failed_uploads += 1
                except Exception as e:
                    logging.error(f"An unexpected error occurred for doc_id: {doc_id if 'doc_id' in locals() else '[unknown]'} (attempt {attempt}): {e}")
                    if attempt == 3:
                        failed_uploads += 1
            iter_end_time = time.time()
            logging.info(f"Iteration for doc_id: {doc_id if 'doc_id' in locals() else '[unknown]'} took {iter_end_time - iter_start_time:.2f} seconds")

        save_uploaded_links(new_uploaded_links) #

        total_end_time = time.time()
        logging.info(f"Total scrape_listing_images call took {total_end_time - total_start_time:.2f} seconds") #

    return {
        "uploaded": successful_uploads,
        "failed": failed_uploads,
        "firestore_docs": uploaded_docs,
    }

UPLOADED_LINKS_FILE = "uploaded_links.json"

def load_uploaded_links():
    if not os.path.exists(UPLOADED_LINKS_FILE):
        return set()
    with open(UPLOADED_LINKS_FILE, "r") as f:
        try:
            return set(json.load(f))
        except Exception:
            return set()

def save_uploaded_links(links):
    with open(UPLOADED_LINKS_FILE, "w") as f:
        json.dump(list(links), f)

# @http
def scrape_http(request):
    try:
        req_data = request.get_json(silent=True)
        if not req_data:
            return jsonify({"error": "Request must be in JSON format."}), 400
        url = req_data.get("url")
        bucket_name = req_data.get("bucket_name")
        firestore_collection = req_data.get("firestore_collection")
        max_items = req_data.get("max_items")
        if not url:
            return jsonify({"error": "Missing required parameter: url"}), 400
        if not bucket_name:
            return jsonify({"error": "Missing required parameter: bucket_name"}), 400
        if not firestore_collection:
            return jsonify({"error": "Missing required parameter: firestore_collection"}), 400
        if max_items is not None:
            try:
                max_items = int(max_items)
            except Exception:
                return jsonify({"error": "max_items must be an integer"}), 400
        result = scrape_listing_images(url, bucket_name, firestore_collection, max_items)
        if "error" in result:
            return jsonify(result), 500
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Internal server error: {e}"}), 500

if __name__ == "__main__":
    app = Flask(__name__)
    # Use Flask's request object for local testing
    app.add_url_rule("/scrape", view_func=lambda: scrape_http(request), methods=["POST"])
    app.run(host="127.0.0.1", port=8080, debug=True)
