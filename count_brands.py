#!/usr/bin/env python3
"""
Script to count brands in the brand_field of a Firestore collection
"""

from google.cloud import firestore
from collections import Counter
import json

def count_brands_in_collection(collection_name):
    """
    Query Firestore collection and count occurrences of each brand in brand_field
    
    Args:
        collection_name (str): Name of the Firestore collection to query
        
    Returns:
        dict: Dictionary with brand names as keys and counts as values
    """
    try:
        # Initialize Firestore client
        db = firestore.Client()
        
        # Get reference to the collection
        collection_ref = db.collection(collection_name)
        
        # Query all documents in the collection
        docs = collection_ref.stream()
        
        # Extract brand names from brand_field
        brands = []
        total_docs = 0
        
        print(f"Querying collection: {collection_name}")
        print("Fetching documents...")
        
        for doc in docs:
            total_docs += 1
            data = doc.to_dict()
            
            # Check if brand_field exists and has a value
            if 'brand_name' in data and data['brand_name']:
                brand = data['brand_name'].strip()
                if brand and brand.lower() != 'unknown':
                    brands.append(brand)
                else:
                    brands.append('unknown')
            else:
                brands.append('missing')
        
        # Count occurrences of each brand
        brand_counts = Counter(brands)
        
        print(f"\nTotal documents processed: {total_docs}")
        print(f"Documents with brand information: {len([b for b in brands if b not in ['missing', 'unknown']])}")
        print(f"Documents with missing brand: {brand_counts.get('missing', 0)}")
        print(f"Documents with unknown brand: {brand_counts.get('unknown', 0)}")
        
        return dict(brand_counts)
        
    except Exception as e:
        print(f"Error querying Firestore: {e}")
        return {}

def main():
    """Main function to run the brand counting script"""
    print("=== Firestore Brand Counter ===\n")
    
    # Get collection name from user
    collection_name = input("Enter Firestore collection name: ").strip()
    
    if not collection_name:
        print("Collection name is required!")
        return
    
    # Count brands
    brand_counts = count_brands_in_collection(collection_name)
    
    if brand_counts:
        print("\n=== Brand Counts ===")
        
        # Sort by count (descending)
        sorted_brands = sorted(brand_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Print results in a nice format
        print(f"{'Brand':<30} {'Count':<10}")
        print("-" * 40)
        
        for brand, count in sorted_brands:
            print(f"{brand:<30} {count:<10}")
        
        # Save results to JSON file
        output_file = f"brand_counts_{collection_name}.json"
        with open(output_file, 'w') as f:
            json.dump(brand_counts, f, indent=2)
        
        print(f"\nResults saved to: {output_file}")
        
        # Summary statistics
        total_brands = len([b for b in brand_counts.keys() if b not in ['missing', 'unknown']])
        print(f"\nSummary:")
        print(f"- Total unique brands: {total_brands}")
        print(f"- Most common brand: {sorted_brands[0][0]} ({sorted_brands[0][1]} items)")
        
        if len(sorted_brands) > 1:
            print(f"- Second most common: {sorted_brands[1][0]} ({sorted_brands[1][1]} items)")
    else:
        print("No results found or an error occurred.")

if __name__ == "__main__":
    main()
