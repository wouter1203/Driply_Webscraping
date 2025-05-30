curl -X POST http://localhost:8080/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.farfetch.com/nl/shopping/men/clothing-2/items.aspx?designer=7466135",
    "bucket_name": "skilled-nation-432314-g6.firebasestorage.app",
    "firestore_collection": "wardrobe",
    "max_items": 3
  }'