#!/usr/bin/env python3
"""
Simple wrapper script to run duplicate detection on your Firestore wardrobe collection.
This script provides easy-to-use functions for common duplicate detection tasks.
"""

from duplicate_detector import DuplicateDetector
import argparse

def detect_only(collection_name="wardrobe", threshold=0.95):
    """Just detect duplicates without removing them."""
    print("🔍 Detecting duplicates in your wardrobe collection...")
    
    with DuplicateDetector(collection_name, threshold) as detector:
        duplicates = detector.find_duplicates()
        similar_images = detector.find_similar_images()
        
        if duplicates:
            print(f"\n✅ Found {len(duplicates)} groups of duplicate images!")
            print(f"📊 Total duplicate documents: {sum(len(docs) for docs in duplicates.values())}")
            
            # Show a summary
            for i, (image_hash, docs) in enumerate(duplicates.items(), 1):
                print(f"\nGroup {i}: {len(docs)} duplicates")
                for j, doc in enumerate(docs):
                    status = "🌟 KEEP" if j == 0 else "🗑️  REMOVE"
                    print(f"  {status} - {doc.get('brand_name', 'unknown')} - {doc.get('name', 'unknown')}")
        else:
            print("🎉 No exact duplicates found!")
        
        if similar_images:
            print(f"\n🔍 Found {len(similar_images)} pairs of similar images (threshold: {threshold})")
        
        # Generate and save report
        report = detector.generate_report(duplicates, similar_images)
        detector.save_report(report, f"wardrobe_duplicates_{collection_name}.txt")
        print(f"\n📄 Detailed report saved to: wardrobe_duplicates_{collection_name}.txt")

def remove_duplicates(collection_name="wardrobe", threshold=0.95, strategy="keep_newest"):
    """Detect and remove duplicates."""
    print("🧹 Removing duplicates from your wardrobe collection...")
    
    with DuplicateDetector(collection_name, threshold) as detector:
        duplicates = detector.find_duplicates()
        
        if not duplicates:
            print("🎉 No duplicates found to remove!")
            return
        
        print(f"\n⚠️  Found {len(duplicates)} groups of duplicates")
        print(f"📊 Total duplicate documents: {sum(len(docs) for docs in duplicates.values())}")
        print(f"💾 Strategy: {strategy}")
        
        # Show what will be removed
        print("\n📋 Summary of what will be removed:")
        total_removed = 0
        for i, (image_hash, docs) in enumerate(duplicates.items(), 1):
            docs_to_remove = docs[1:]  # All except first
            total_removed += len(docs_to_remove)
            print(f"  Group {i}: Removing {len(docs_to_remove)} duplicates")
            for doc in docs_to_remove:
                print(f"    🗑️  {doc.get('brand_name', 'unknown')} - {doc.get('name', 'unknown')}")
        
        print(f"\n💀 Total documents to be removed: {total_removed}")
        
        # Ask for confirmation
        response = input("\n❓ Do you want to proceed with removal? (y/N): ")
        
        if response.lower() == 'y':
            print("\n🚀 Proceeding with removal...")
            results = detector.remove_duplicates(duplicates, strategy)
            
            print(f"\n✅ Removal completed!")
            print(f"📊 Removed: {results['total_removed']} documents")
            print(f"📊 Kept: {len(results['kept_docs'])} documents")
            
            if results['errors']:
                print(f"⚠️  Errors: {len(results['errors'])}")
                for error in results['errors'][:3]:  # Show first 3 errors
                    print(f"    {error}")
            
            # Generate final report
            remaining_duplicates = detector.find_duplicates()
            if remaining_duplicates:
                print(f"\n⚠️  {len(remaining_duplicates)} groups still have duplicates")
            else:
                print("\n🎉 All duplicates have been removed!")
                
            report = detector.generate_report(remaining_duplicates)
            detector.save_report(report, f"wardrobe_after_cleanup_{collection_name}.txt")
            print(f"📄 Cleanup report saved to: wardrobe_after_cleanup_{collection_name}.txt")
            
        else:
            print("❌ Operation cancelled.")

def main():
    parser = argparse.ArgumentParser(
        description="Easy duplicate detection for your Firestore wardrobe collection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Just detect duplicates (safe, read-only)
  python run_duplicate_detection.py --detect
  
  # Remove duplicates (interactive confirmation)
  python run_duplicate_detection.py --remove
  
  # Use different collection and threshold
  python run_duplicate_detection.py --detect --collection test_wardrobe --threshold 0.90
        """
    )
    
    parser.add_argument("--detect", action="store_true", help="Detect duplicates only (safe)")
    parser.add_argument("--remove", action="store_true", help="Detect and remove duplicates")
    parser.add_argument("--collection", default="wardrobe", help="Firestore collection name (default: wardrobe)")
    parser.add_argument("--threshold", type=float, default=0.95, help="Similarity threshold 0.0-1.0 (default: 0.95)")
    parser.add_argument("--strategy", choices=["keep_newest", "keep_oldest", "keep_first"], 
                       default="keep_newest", help="Strategy when removing duplicates (default: keep_newest)")
    
    args = parser.parse_args()
    
    if not args.detect and not args.remove:
        print("❌ Please specify either --detect or --remove")
        parser.print_help()
        return
    
    if args.detect and args.remove:
        print("❌ Please specify only one action: --detect OR --remove")
        return
    
    print("🚀 Driply Duplicate Detection Tool")
    print("=" * 40)
    print(f"Collection: {args.collection}")
    print(f"Threshold: {args.threshold}")
    print(f"Strategy: {args.strategy}")
    print("=" * 40)
    
    try:
        if args.detect:
            detect_only(args.collection, args.threshold)
        elif args.remove:
            remove_duplicates(args.collection, args.threshold, args.strategy)
            
    except KeyboardInterrupt:
        print("\n\n❌ Operation interrupted by user")
    except Exception as e:
        print(f"\n💥 Error occurred: {e}")
        print("Please check your Firestore credentials and collection name")

if __name__ == "__main__":
    main()
