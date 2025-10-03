import os
import json
import hashlib
from typing import List, Dict, Tuple, Set
from collections import defaultdict
import requests
from PIL import Image
import numpy as np
from google.cloud import firestore
from loguru import logger
import argparse
from pathlib import Path
import tempfile
import shutil

# Configure loguru for concise logs
logger.remove()
logger.add(lambda msg: print(msg, end=""), format="<level>{level}</level> | {message}\n", colorize=True)

class DuplicateDetector:
    def __init__(self, collection_name: str = "wardrobe", similarity_threshold: float = 0.95):
        """
        Initialize the duplicate detector.
        
        Args:
            collection_name: Name of the Firestore collection
            similarity_threshold: Threshold for considering images as duplicates (0.0 to 1.0)
        """
        self.collection_name = collection_name
        self.similarity_threshold = similarity_threshold
        self.db = firestore.Client()
        self.temp_dir = None
        
    def __enter__(self):
        """Context manager entry - create temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup temp directory."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def get_collection_documents(self) -> List[Dict]:
        """Fetch all documents from the Firestore collection."""
        logger.info(f"Fetching documents from collection: {self.collection_name}")
        
        docs = []
        collection_ref = self.db.collection(self.collection_name)
        
        try:
            for doc in collection_ref.stream():
                doc_data = doc.to_dict()
                doc_data['doc_id'] = doc.id
                docs.append(doc_data)
            
            logger.info(f"Found {len(docs)} documents")
            return docs
        except Exception as e:
            logger.error(f"Error fetching documents: {e}")
            return []
    
    def download_image(self, image_url: str, filename: str) -> str:
        """Download an image from URL and save to temp directory."""
        try:
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            filepath = os.path.join(self.temp_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            return filepath
        except Exception as e:
            logger.error(f"Failed to download {image_url}: {e}")
            return None
    
    def calculate_image_hash(self, image_path: str) -> str:
        """Calculate perceptual hash of an image."""
        try:
            with Image.open(image_path) as img:
                # Convert to grayscale and resize for consistent hashing
                img = img.convert('L').resize((8, 8), Image.Resampling.LANCZOS)
                pixels = np.array(img)
                
                # Calculate average pixel value
                avg = pixels.mean()
                
                # Create hash based on pixels above/below average
                hash_value = 0
                for i in range(8):
                    for j in range(8):
                        if pixels[i, j] > avg:
                            hash_value |= 1 << (i * 8 + j)
                
                return format(hash_value, '016x')
        except Exception as e:
            logger.error(f"Error calculating hash for {image_path}: {e}")
            return None
    
    def calculate_image_similarity(self, hash1: str, hash2: str) -> float:
        """Calculate similarity between two image hashes using Hamming distance."""
        if not hash1 or not hash2:
            return 0.0
        
        # Convert hex strings to binary and calculate Hamming distance
        bin1 = bin(int(hash1, 16))[2:].zfill(64)
        bin2 = bin(int(hash2, 16))[2:].zfill(64)
        
        hamming_distance = sum(c1 != c2 for c1, c2 in zip(bin1, bin2))
        
        # Convert to similarity (0.0 to 1.0)
        similarity = 1.0 - (hamming_distance / 64.0)
        return similarity
    
    def find_duplicates(self) -> Dict[str, List[Dict]]:
        """Find duplicate images in the collection."""
        logger.info("Starting duplicate detection...")
        
        documents = self.get_collection_documents()
        if not documents:
            logger.warning("No documents found in collection")
            return {}
        
        # Group documents by image hash
        hash_groups = defaultdict(list)
        processed_count = 0
        
        for doc in documents:
            if 'imageUrl' not in doc:
                logger.warning(f"Document {doc.get('doc_id', 'unknown')} missing imageUrl")
                continue
            
            try:
                # Download image and calculate hash
                filename = f"{doc['doc_id']}.jpg"
                image_path = self.download_image(doc['imageUrl'], filename)
                
                if image_path:
                    image_hash = self.calculate_image_hash(image_path)
                    if image_hash:
                        hash_groups[image_hash].append(doc)
                        processed_count += 1
                        
                        if processed_count % 10 == 0:
                            logger.info(f"Processed {processed_count}/{len(documents)} images")
                
            except Exception as e:
                logger.error(f"Error processing document {doc.get('doc_id', 'unknown')}: {e}")
                continue
        
        logger.info(f"Successfully processed {processed_count} images")
        
        # Find groups with multiple documents (duplicates)
        duplicates = {}
        for image_hash, docs in hash_groups.items():
            if len(docs) > 1:
                duplicates[image_hash] = docs
        
        logger.info(f"Found {len(duplicates)} groups of duplicate images")
        return duplicates
    
    def find_similar_images(self) -> List[Tuple[Dict, Dict, float]]:
        """Find images that are similar but not exact duplicates."""
        logger.info("Finding similar images...")
        
        documents = self.get_collection_documents()
        if not documents:
            return []
        
        # Download all images and calculate hashes
        doc_hashes = {}
        processed_count = 0
        
        for doc in documents:
            if 'imageUrl' not in doc:
                continue
                
            try:
                filename = f"{doc['doc_id']}.jpg"
                image_path = self.download_image(doc['imageUrl'], filename)
                
                if image_path:
                    image_hash = self.calculate_image_hash(image_path)
                    if image_hash:
                        doc_hashes[doc['doc_id']] = (doc, image_hash)
                        processed_count += 1
                        
                        if processed_count % 10 == 0:
                            logger.info(f"Processed {processed_count}/{len(documents)} images")
                            
            except Exception as e:
                logger.error(f"Error processing document {doc.get('doc_id', 'unknown')}: {e}")
                continue
        
        # Compare all pairs for similarity
        similar_pairs = []
        doc_ids = list(doc_hashes.keys())
        
        for i in range(len(doc_ids)):
            for j in range(i + 1, len(doc_ids)):
                doc1_id = doc_ids[i]
                doc2_id = doc_ids[j]
                
                doc1, hash1 = doc_hashes[doc1_id]
                doc2, hash2 = doc_hashes[doc2_id]
                
                similarity = self.calculate_image_similarity(hash1, hash2)
                
                if similarity >= self.similarity_threshold:
                    similar_pairs.append((doc1, doc2, similarity))
        
        logger.info(f"Found {len(similar_pairs)} pairs of similar images")
        return similar_pairs
    
    def remove_duplicates(self, duplicates: Dict[str, List[Dict]], keep_strategy: str = "keep_newest") -> Dict:
        """
        Remove duplicate documents from Firestore.
        
        Args:
            duplicates: Dictionary of duplicate groups
            keep_strategy: Strategy for keeping documents ("keep_newest", "keep_oldest", "keep_first")
        
        Returns:
            Dictionary with removal results
        """
        logger.info(f"Removing duplicates using strategy: {keep_strategy}")
        
        results = {
            "total_groups": len(duplicates),
            "total_removed": 0,
            "removed_docs": [],
            "kept_docs": [],
            "errors": []
        }
        
        for image_hash, docs in duplicates.items():
            try:
                if keep_strategy == "keep_newest":
                    # Keep the document with the most recent timestamp (if available)
                    # For now, just keep the first one
                    docs_to_keep = [docs[0]]
                    docs_to_remove = docs[1:]
                elif keep_strategy == "keep_oldest":
                    docs_to_keep = [docs[-1]]
                    docs_to_remove = docs[:-1]
                else:  # keep_first
                    docs_to_keep = [docs[0]]
                    docs_to_remove = docs[1:]
                
                # Remove duplicate documents
                for doc in docs_to_remove:
                    try:
                        doc_ref = self.db.collection(self.collection_name).document(doc['doc_id'])
                        doc_ref.delete()
                        
                        results["removed_docs"].append({
                            "doc_id": doc['doc_id'],
                            "brand_name": doc.get('brand_name', 'unknown'),
                            "name": doc.get('name', 'unknown'),
                            "imageUrl": doc.get('imageUrl', 'unknown')
                        })
                        results["total_removed"] += 1
                        
                        logger.info(f"Removed duplicate: {doc['doc_id']}")
                        
                    except Exception as e:
                        error_msg = f"Error removing document {doc['doc_id']}: {e}"
                        logger.error(error_msg)
                        results["errors"].append(error_msg)
                
                # Track kept documents
                for doc in docs_to_keep:
                    results["kept_docs"].append({
                        "doc_id": doc['doc_id'],
                        "brand_name": doc.get('brand_name', 'unknown'),
                        "name": doc.get('name', 'unknown'),
                        "imageUrl": doc.get('imageUrl', 'unknown')
                    })
                    
            except Exception as e:
                error_msg = f"Error processing duplicate group: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
        
        logger.info(f"Removed {results['total_removed']} duplicate documents")
        return results
    
    def generate_report(self, duplicates: Dict[str, List[Dict]], similar_images: List[Tuple[Dict, Dict, float]] = None) -> str:
        """Generate a detailed report of duplicates and similar images."""
        report = []
        report.append("=" * 60)
        report.append("DUPLICATE DETECTION REPORT")
        report.append("=" * 60)
        report.append(f"Collection: {self.collection_name}")
        report.append(f"Similarity Threshold: {self.similarity_threshold}")
        report.append("")
        
        # Exact duplicates
        report.append("EXACT DUPLICATES:")
        report.append("-" * 30)
        if duplicates:
            for i, (image_hash, docs) in enumerate(duplicates.items(), 1):
                report.append(f"Group {i} ({len(docs)} items):")
                for j, doc in enumerate(docs):
                    status = "KEEP" if j == 0 else "REMOVE"
                    report.append(f"  {j+1}. [{status}] {doc['doc_id']} - {doc.get('brand_name', 'unknown')} - {doc.get('name', 'unknown')}")
                report.append("")
        else:
            report.append("No exact duplicates found.")
            report.append("")
        
        # Similar images
        if similar_images:
            report.append("SIMILAR IMAGES:")
            report.append("-" * 30)
            for i, (doc1, doc2, similarity) in enumerate(similar_images, 1):
                report.append(f"Pair {i} (Similarity: {similarity:.3f}):")
                report.append(f"  Doc1: {doc1['doc_id']} - {doc1.get('brand_name', 'unknown')} - {doc1.get('name', 'unknown')}")
                report.append(f"  Doc2: {doc2['doc_id']} - {doc2.get('brand_name', 'unknown')} - {doc2.get('name', 'unknown')}")
                report.append("")
        
        return "\n".join(report)
    
    def save_report(self, report: str, filename: str = "duplicate_report.txt"):
        """Save the report to a file."""
        try:
            with open(filename, 'w') as f:
                f.write(report)
            logger.info(f"Report saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving report: {e}")

def main():
    parser = argparse.ArgumentParser(description="Detect and handle duplicates in Firestore collection")
    parser.add_argument("--collection", default="wardrobe", help="Firestore collection name")
    parser.add_argument("--threshold", type=float, default=0.95, help="Similarity threshold (0.0 to 1.0)")
    parser.add_argument("--action", choices=["detect", "remove", "report"], default="detect", 
                       help="Action to perform")
    parser.add_argument("--strategy", choices=["keep_newest", "keep_oldest", "keep_first"], 
                       default="keep_newest", help="Strategy for keeping documents when removing duplicates")
    parser.add_argument("--output", default="duplicate_report.txt", help="Output file for report")
    
    args = parser.parse_args()
    
    logger.info("Starting duplicate detection process...")
    
    with DuplicateDetector(args.collection, args.threshold) as detector:
        if args.action == "detect":
            # Just detect and report
            duplicates = detector.find_duplicates()
            similar_images = detector.find_similar_images()
            
            report = detector.generate_report(duplicates, similar_images)
            print(report)
            
            detector.save_report(report, args.output)
            
        elif args.action == "remove":
            # Detect and remove duplicates
            duplicates = detector.find_duplicates()
            
            if duplicates:
                print(f"Found {len(duplicates)} groups of duplicates")
                response = input("Do you want to proceed with removal? (y/N): ")
                
                if response.lower() == 'y':
                    results = detector.remove_duplicates(duplicates, args.strategy)
                    print(f"Removed {results['total_removed']} duplicate documents")
                    
                    # Generate final report
                    remaining_duplicates = detector.find_duplicates()
                    report = detector.generate_report(remaining_duplicates)
                    detector.save_report(report, args.output)
                else:
                    print("Operation cancelled.")
            else:
                print("No duplicates found.")
                
        elif args.action == "report":
            # Generate report from existing data
            duplicates = detector.find_duplicates()
            similar_images = detector.find_similar_images()
            
            report = detector.generate_report(duplicates, similar_images)
            print(report)
            detector.save_report(report, args.output)

if __name__ == "__main__":
    main()
