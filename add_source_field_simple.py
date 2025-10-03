#!/usr/bin/env python3
"""
Simple script to add "source": "Online" field to each item in the wardrobe collection.

Usage:
    python add_source_field_simple.py [--collection COLLECTION_NAME] [--dry-run]

Examples:
    python add_source_field_simple.py                           # Update 'wardrobe' collection
    python add_source_field_simple.py --collection test        # Update 'test' collection
    python add_source_field_simple.py --dry-run                # Preview changes without updating
"""

import argparse
import os
from google.cloud import firestore
from loguru import logger
import time

# Configure loguru for concise logs
logger.remove()
logger.add(lambda msg: print(msg, end=""), format="<level>{level}</level> | {message}\n", colorize=True)

def add_source_field_to_wardrobe(collection_name="wardrobe", dry_run=False):
    """
    Add "source": "Online" field to all documents in the specified collection.
    
    Args:
        collection_name (str): Name of the Firestore collection (default: "wardrobe")
        dry_run (bool): If True, only preview changes without updating (default: False)
    """
    mode = "🔍 DRY RUN" if dry_run else "🚀 UPDATE"
    logger.info(f"{mode}: Adding 'source' field to '{collection_name}' collection...")
    
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
        
        # Process documents
        processed = 0
        would_update = 0
        skipped = 0
        errors = 0
        
        start_time = time.time()
        
        # Get all documents
        docs = list(collection_ref.stream())
        
        for doc in docs:
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
                
                # Count what would be updated
                would_update += 1
                processed += 1
                
                # Actually update if not dry run
                if not dry_run:
                    doc.reference.update({
                        'source': 'Online'
                    })
                
                # Log progress every 100 documents
                if processed % 100 == 0:
                    elapsed = time.time() - start_time
                    rate = processed / elapsed if elapsed > 0 else 0
                    eta = (total_docs - processed) / rate if rate > 0 else 0
                    logger.info(f"📈 Progress: {processed}/{total_docs} ({processed/total_docs*100:.1f}%) - "
                              f"Rate: {rate:.1f} docs/sec - ETA: {eta:.1f}s")
                
            except Exception as e:
                errors += 1
                logger.error(f"❌ Error processing document {doc.id}: {e}")
                processed += 1
        
        # Final summary
        elapsed_time = time.time() - start_time
        action = "Preview" if dry_run else "Update"
        logger.info(f"\n🎉 {action} completed!")
        logger.info(f"📊 Summary:")
        logger.info(f"   • Total documents: {total_docs}")
        logger.info(f"   • Processed: {processed}")
        if dry_run:
            logger.info(f"   • Would update: {would_update}")
        else:
            logger.info(f"   • Updated: {would_update}")
        logger.info(f"   • Skipped (already had source='Online'): {skipped}")
        logger.info(f"   • Errors: {errors}")
        logger.info(f"   • Time taken: {elapsed_time:.2f} seconds")
        
        if errors > 0:
            logger.warning(f"⚠️  {errors} documents had errors during processing")
        
        if dry_run and would_update > 0:
            logger.info(f"\n💡 Run without --dry-run to actually update {would_update} documents")
        
        return {
            "total_documents": total_docs,
            "processed": processed,
            "updated": would_update,
            "skipped": skipped,
            "errors": errors,
            "elapsed_time": elapsed_time
        }
        
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        raise

def main():
    """Main function to run the script"""
    parser = argparse.ArgumentParser(
        description="Add 'source': 'Online' field to Firestore collection documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--collection", 
        default="wardrobe",
        help="Firestore collection name (default: wardrobe)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without actually updating documents"
    )
    
    args = parser.parse_args()
    
    logger.info("=== Add Source Field to Wardrobe Collection ===\n")
    logger.info(f"📋 Configuration:")
    logger.info(f"   • Collection: {args.collection}")
    logger.info(f"   • Mode: {'DRY RUN (preview only)' if args.dry_run else 'UPDATE'}")
    
    try:
        # Run the update
        result = add_source_field_to_wardrobe(args.collection, args.dry_run)
        
        if result and result['errors'] == 0:
            if args.dry_run:
                logger.info("✅ Preview completed successfully!")
            else:
                logger.info("✅ All documents updated successfully!")
        elif result:
            logger.warning("⚠️  Operation completed with some errors")
        else:
            logger.error("❌ Operation failed")
            
    except KeyboardInterrupt:
        logger.info("\n⏹️  Operation interrupted by user")
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")

if __name__ == "__main__":
    main()
