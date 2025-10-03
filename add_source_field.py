#!/usr/bin/env python3
"""
Script to add "source": "Online" field to each item in the wardrobe collection.

This script will:
1. Connect to Firestore
2. Query all documents in the wardrobe collection
3. Add the "source": "Online" field to each document
4. Provide progress updates and summary
"""

import os
from google.cloud import firestore
from loguru import logger
import time

# Configure loguru for concise logs
logger.remove()
logger.add(lambda msg: print(msg, end=""), format="<level>{level}</level> | {message}\n", colorize=True)

def add_source_field_to_wardrobe(collection_name="wardrobe", batch_size=500):
    """
    Add "source": "Online" field to all documents in the specified collection.
    
    Args:
        collection_name (str): Name of the Firestore collection (default: "wardrobe")
        batch_size (int): Number of documents to process in each batch (default: 500)
    """
    logger.info(f"🚀 Starting to add 'source' field to '{collection_name}' collection...")
    
    try:
        # Initialize Firestore client
        db = firestore.Client()
        collection_ref = db.collection(collection_name)
        
        # Get total count of documents
        total_docs = len(list(collection_ref.stream()))
        logger.info(f"📊 Total documents in collection: {total_docs}")
        
        if total_docs == 0:
            logger.warning(f"⚠️  No documents found in '{collection_name}' collection")
            return
        
        # Process documents in batches
        processed = 0
        updated = 0
        skipped = 0
        errors = 0
        
        start_time = time.time()
        
        # Get all documents
        docs = list(collection_ref.stream())
        
        for i, doc in enumerate(docs):
            try:
                doc_data = doc.to_dict()
                
                # Check if source field already exists
                if 'source' in doc_data:
                    if doc_data['source'] == 'Online':
                        skipped += 1
                        logger.debug(f"⏭️  Document {doc.id} already has source='Online', skipping")
                        continue
                    else:
                        logger.debug(f"🔄 Document {doc.id} has source='{doc_data['source']}', will update to 'Online'")
                
                # Update the document with source field
                doc.reference.update({
                    'source': 'Online'
                })
                
                updated += 1
                processed += 1
                
                # Log progress every 100 documents
                if processed % 100 == 0:
                    elapsed = time.time() - start_time
                    rate = processed / elapsed if elapsed > 0 else 0
                    eta = (total_docs - processed) / rate if rate > 0 else 0
                    logger.info(f"📈 Progress: {processed}/{total_docs} ({processed/total_docs*100:.1f}%) - "
                              f"Rate: {rate:.1f} docs/sec - ETA: {eta:.1f}s")
                
            except Exception as e:
                errors += 1
                logger.error(f"❌ Error updating document {doc.id}: {e}")
                processed += 1
        
        # Final summary
        elapsed_time = time.time() - start_time
        logger.info(f"\n🎉 Update completed!")
        logger.info(f"📊 Summary:")
        logger.info(f"   • Total documents: {total_docs}")
        logger.info(f"   • Processed: {processed}")
        logger.info(f"   • Updated: {updated}")
        logger.info(f"   • Skipped (already had source='Online'): {skipped}")
        logger.info(f"   • Errors: {errors}")
        logger.info(f"   • Time taken: {elapsed_time:.2f} seconds")
        
        if errors > 0:
            logger.warning(f"⚠️  {errors} documents had errors during update")
        
        return {
            "total_documents": total_docs,
            "processed": processed,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
            "elapsed_time": elapsed_time
        }
        
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        raise

def main():
    """Main function to run the script"""
    logger.info("=== Add Source Field to Wardrobe Collection ===\n")
    
    # Get collection name from user input
    collection_name = input("Enter Firestore collection name (default: wardrobe): ").strip()
    if not collection_name:
        collection_name = "wardrobe"
    
    # Get batch size from user input
    batch_size_input = input("Enter batch size (default: 500): ").strip()
    try:
        batch_size = int(batch_size_input) if batch_size_input else 500
    except ValueError:
        logger.warning("Invalid batch size, using default: 500")
        batch_size = 500
    
    # Confirm before proceeding
    logger.info(f"\n📋 Configuration:")
    logger.info(f"   • Collection: {collection_name}")
    logger.info(f"   • Batch size: {batch_size}")
    
    confirm = input(f"\n⚠️  This will add 'source': 'Online' to ALL documents in '{collection_name}' collection. Continue? (y/N): ").strip().lower()
    
    if confirm not in ['y', 'yes']:
        logger.info("❌ Operation cancelled by user")
        return
    
    try:
        # Run the update
        result = add_source_field_to_wardrobe(collection_name, batch_size)
        
        if result and result['errors'] == 0:
            logger.info("✅ All documents updated successfully!")
        elif result:
            logger.warning("⚠️  Update completed with some errors")
        else:
            logger.error("❌ Update failed")
            
    except KeyboardInterrupt:
        logger.info("\n⏹️  Operation interrupted by user")
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")

if __name__ == "__main__":
    main()
