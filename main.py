import os
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
from rembg import remove, new_session
from loguru import logger

# Configure loguru for concise logs
logger.remove()
logger.add(lambda msg: print(msg, end=""), format="<level>{level}</level> | {message}\n", colorize=True)

# It's good practice to define the User-Agent globally or at the top of the function
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def download_image(img_url_tuple, max_retries=3):
    idx, img_url, folder_name = img_url_tuple
    for attempt in range(1, max_retries + 1):
        try:
            logger.debug(f"Downloading {idx} (try {attempt}): {img_url}")
            img_data = requests.get(img_url, timeout=10).content
            img_path = os.path.join(folder_name, f"image_{idx}.jpg")
            with open(img_path, "wb") as f:
                f.write(img_data)
            logger.info(f"Downloaded {idx}")
            return True
        except Exception as e:
            logger.warning(f"Failed {img_url} (try {attempt}): {e}")
            if attempt == max_retries:
                logger.error(f"Giving up {img_url}")
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
    logger.info(f"Scraping: {url}")

    total_start_time = time.time()

    uploaded_links = load_uploaded_links()
    new_uploaded_links = set(uploaded_links)

    with requests.Session() as session:
        session.headers.update(HEADERS)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            page.goto(url, timeout=60000, wait_until="domcontentloaded")

            scroll_pause = 0.1
            scroll_step = 600
            stuck_count = 0
            stuck_limit = 3

            current_position = 0
            last_height = page.evaluate("() => document.body.scrollHeight")

            while stuck_count < stuck_limit:
                current_position += scroll_step
                page.evaluate(f"window.scrollTo(0, {current_position});")
                page.wait_for_timeout(int(scroll_pause * 1000))
                new_height = page.evaluate("() => document.body.scrollHeight")
                logger.debug(f"Scroll: position={current_position}, height={new_height}")

                if new_height > last_height:
                    stuck_count = 0
                else:
                    stuck_count += 1
                    # Give the page a bit more time to load if stuck
                    page.wait_for_timeout(500)

                # If we've reached or passed the bottom, scroll to the bottom explicitly
                if current_position >= new_height:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                    page.wait_for_timeout(200)
                    new_height = page.evaluate("() => document.body.scrollHeight")
                    logger.debug(f"Force scroll to bottom: height={new_height}")
                    if new_height == last_height:
                        stuck_count += 1
                    else:
                        stuck_count = 0
                    current_position = new_height

                last_height = new_height

            try:
                page.wait_for_selector('img.ltr-io0g65', timeout=10000)
                logger.debug("Images loaded.")
            except Exception as e:
                logger.error(f"Timeout: {e}")
                browser.close()
                return {"error": "Timeout waiting for images."}
            page_content = page.content()
            browser.close()

        soup = BeautifulSoup(page_content, "html.parser")
        img_tags = soup.find_all("img")
        logger.debug(f"Found {len(img_tags)} imgs.")
        img_urls = []
        for img in img_tags:
            src = img.get("src")
            if (
                src
                and src.startswith("https://cdn-images.farfetch-contents.com/")
                and src.endswith(".jpg")
            ):
                img_urls.append(src)
                logger.debug(f"Add img: {src}")
                if max_items and len(img_urls) >= max_items:
                    break

        brands = [p.get_text(strip=True) for p in soup.find_all("p", {"data-component": "ProductCardBrandName"})]
        product_names = [p.get_text(strip=True) for p in soup.find_all("p", {"data-component": "ProductCardDescription"})]

        if max_items:
            brands = brands[:max_items]
            product_names = product_names[:max_items]

        if not img_urls:
            logger.warning("No images found.")
            return {"error": "No product images found."}

        db = firestore.Client()
        successful_uploads = 0
        failed_uploads = 0
        uploaded_docs = []

        rembg_session = new_session("birefnet-general")

        for idx, (img_url, brand, product) in enumerate(zip(img_urls, brands, product_names)):
            iter_start_time = time.time()
            if img_url in uploaded_links:
                logger.info(f"Skip uploaded: [already_uploaded]")
                continue
            attempt = 0
            success = False
            while attempt < 3 and not success:
                attempt += 1
                logger.info(f"Try {attempt}: {idx + 1}/{len(img_urls)}")
                try:
                    response = session.get(img_url, timeout=10, stream=True)
                    response.raise_for_status()
                    img_data = response.content
                    
                    start_background_removal = time.time()
                    
                    logger.info(f"Starting background removal after: {start_background_removal - iter_start_time:.2f}s")

                    img_data = remove(
                        img_data,
                        session=rembg_session,
                        alpha_matting=True,
                        alpha_matting_foreground_threshold=240,
                        alpha_matting_background_threshold=10,
                        alpha_matting_erode_size=10,
                    )
                    
                    end_background_removal = time.time()
                    
                    logger.info(f"Background removal done in: {end_background_removal - start_background_removal:.2f}s")

                    doc_ref = db.collection(firestore_collection).document()
                    doc_id = doc_ref.id
                    folder_prefix = "wardrobe"
                    blob_name = f"{folder_prefix}/{doc_id}.jpg"
                    logger.info(f"Uploading: {doc_id}")
                    public_url = upload_image_to_gcs(img_data, bucket_name, blob_name)
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
                    logger.error(f"Download fail: {doc_id if 'doc_id' in locals() else '[unknown]'} ({attempt}): {e}")
                    if attempt == 3:
                        failed_uploads += 1
                except Exception as e:
                    logger.error(f"Error: {doc_id if 'doc_id' in locals() else '[unknown]'} ({attempt}): {e}")
                    if attempt == 3:
                        failed_uploads += 1
            iter_end_time = time.time()
            logger.debug(f"Iter {doc_id if 'doc_id' in locals() else '[unknown]'}: {iter_end_time - iter_start_time:.2f}s")

        save_uploaded_links(new_uploaded_links)

        total_end_time = time.time()
        logger.info(f"Done in {total_end_time - total_start_time:.2f}s")

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
        bucket_name = "skilled-nation-432314-g6.firebasestorage.app"
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
