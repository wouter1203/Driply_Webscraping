#!/usr/bin/env python3
"""
Script to analyze wardrobe images for colors and patterns
"""

import json
import os
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Optional
import numpy as np
from PIL import Image, ImageFilter
import colorsys
from google.cloud import firestore
from loguru import logger

class WardrobeImageAnalyzer:
    """Analyzes wardrobe images for colors and patterns"""
    
    def __init__(self):
        """Initialize the analyzer"""
        # Define color categories
        self.color_categories = {
            'red': [(0, 50), (340, 360)],      # Red hues
            'orange': [(10, 30)],               # Orange hues
            'yellow': [(45, 75)],               # Yellow hues
            'green': [(90, 150)],               # Green hues
            'blue': [(200, 250)],               # Blue hues
            'purple': [(260, 300)],             # Purple hues
            'pink': [(320, 340)],               # Pink hues
            'brown': [(15, 45), (30, 60)],     # Brown hues
            'gray': [(0, 360)],                 # Gray (low saturation)
            'white': [(0, 360)],                # White (high value, low saturation)
            'black': [(0, 360)]                 # Black (low value)
        }
        
        # Define pattern categories
        self.pattern_categories = {
            'plain': 'solid_color',
            'striped': 'horizontal_or_vertical_lines',
            'floral': 'flower_patterns',
            'geometric': 'geometric_shapes',
            'polka_dot': 'circular_patterns',
            'checkered': 'grid_pattern',
            'embroidered': 'detailed_embroidery',
            'printed': 'printed_designs',
            'textured': 'texture_variations'
        }
    
    def analyze_image_colors(self, image_path: str) -> Dict[str, any]:
        """
        Analyze the dominant colors in an image
        
        Args:
            image_path (str): Path to the image file
            
        Returns:
            dict: Color analysis results
        """
        try:
            # Open and resize image for faster processing
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize for faster processing
                img = img.resize((100, 100), Image.Resampling.LANCZOS)
                
                # Convert to numpy array
                img_array = np.array(img)
                
                # Reshape to get all pixels
                pixels = img_array.reshape(-1, 3)
                
                # Convert RGB to HSV
                hsv_pixels = []
                for pixel in pixels:
                    h, s, v = colorsys.rgb_to_hsv(pixel[0]/255, pixel[1]/255, pixel[2]/255)
                    hsv_pixels.append([h*360, s*100, v*100])
                
                hsv_pixels = np.array(hsv_pixels)
                
                # Analyze dominant colors
                dominant_colors = self._get_dominant_colors(hsv_pixels)
                
                # Categorize colors
                color_distribution = self._categorize_colors(hsv_pixels)
                
                # Calculate color statistics
                avg_saturation = np.mean(hsv_pixels[:, 1])
                avg_value = np.mean(hsv_pixels[:, 2])
                color_variety = len(set([tuple(pixel) for pixel in pixels]))
                
                return {
                    'dominant_colors': dominant_colors,
                    'color_distribution': color_distribution,
                    'avg_saturation': round(avg_saturation, 2),
                    'avg_value': round(avg_value, 2),
                    'color_variety': color_variety,
                    'primary_color': self._get_primary_color(color_distribution)
                }
                
        except Exception as e:
            logger.error(f"Error analyzing colors for {image_path}: {e}")
            return {}
    
    def analyze_image_patterns(self, image_path: str) -> Dict[str, any]:
        """
        Analyze patterns in an image
        
        Args:
            image_path (str): Path to the image file
            
        Returns:
            dict: Pattern analysis results
        """
        try:
            with Image.open(image_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize for pattern analysis
                img = img.resize((200, 200), Image.Resampling.LANCZOS)
                
                # Convert to grayscale for edge detection
                gray_img = img.convert('L')
                
                # Apply edge detection
                edges = gray_img.filter(ImageFilter.FIND_EDGES)
                edge_array = np.array(edges)
                
                # Analyze edges for patterns
                edge_density = np.mean(edge_array > 50)
                
                # Detect horizontal and vertical lines
                horizontal_lines = self._detect_lines(edge_array, 'horizontal')
                vertical_lines = self._detect_lines(edge_array, 'vertical')
                
                # Detect circular patterns (polka dots)
                circles = self._detect_circles(edge_array)
                
                # Pattern classification
                pattern_type = self._classify_pattern(
                    edge_density, horizontal_lines, vertical_lines, circles
                )
                
                return {
                    'pattern_type': pattern_type,
                    'edge_density': round(edge_density, 3),
                    'horizontal_lines': horizontal_lines,
                    'vertical_lines': vertical_lines,
                    'circles_detected': circles,
                    'complexity_score': self._calculate_complexity(edge_array)
                }
                
        except Exception as e:
            logger.error(f"Error analyzing patterns for {image_path}: {e}")
            return {}
    
    def _get_dominant_colors(self, hsv_pixels: np.ndarray) -> List[Tuple[str, float]]:
        """Get the most dominant colors in the image"""
        # Group similar colors
        color_groups = defaultdict(int)
        
        for h, s, v in hsv_pixels:
            if s < 15:  # Low saturation = grayscale
                if v < 30:
                    color_groups['black'] += 1
                elif v > 70:
                    color_groups['white'] += 1
                else:
                    color_groups['gray'] += 1
            else:
                # Find closest color category
                for color_name, hue_ranges in self.color_categories.items():
                    if color_name in ['gray', 'white', 'black']:
                        continue
                    
                    for hue_min, hue_max in hue_ranges:
                        if hue_min <= h <= hue_max:
                            color_groups[color_name] += 1
                            break
                    else:
                        continue
                    break
        
        # Return top 3 dominant colors
        sorted_colors = sorted(color_groups.items(), key=lambda x: x[1], reverse=True)
        total_pixels = len(hsv_pixels)
        
        return [(color, round(count/total_pixels*100, 1)) for color, count in sorted_colors[:3]]
    
    def _categorize_colors(self, hsv_pixels: np.ndarray) -> Dict[str, int]:
        """Categorize colors into predefined categories"""
        categories = defaultdict(int)
        
        for h, s, v in hsv_pixels:
            if s < 15:  # Low saturation
                if v < 30:
                    categories['black'] += 1
                elif v > 70:
                    categories['white'] += 1
                else:
                    categories['gray'] += 1
            else:
                # Find color category
                for color_name, hue_ranges in self.color_categories.items():
                    if color_name in ['gray', 'white', 'black']:
                        continue
                    
                    for hue_min, hue_max in hue_ranges:
                        if hue_min <= h <= hue_max:
                            categories[color_name] += 1
                            break
                    else:
                        continue
                    break
        
        return dict(categories)
    
    def _get_primary_color(self, color_distribution: Dict[str, int]) -> str:
        """Get the primary color from distribution"""
        if not color_distribution:
            return 'unknown'
        
        return max(color_distribution.items(), key=lambda x: x[1])[0]
    
    def _detect_lines(self, edge_array: np.ndarray, direction: str) -> int:
        """Detect lines in a specific direction"""
        if direction == 'horizontal':
            # Sum along rows
            line_strength = np.sum(edge_array > 50, axis=1)
        else:  # vertical
            # Sum along columns
            line_strength = np.sum(edge_array > 50, axis=0)
        
        # Count strong lines
        strong_lines = np.sum(line_strength > np.mean(line_strength) + np.std(line_strength))
        return int(strong_lines)
    
    def _detect_circles(self, edge_array: np.ndarray) -> int:
        """Detect circular patterns (simplified)"""
        # Simple circle detection using edge density in circular regions
        height, width = edge_array.shape
        center_y, center_x = height // 2, width // 2
        
        # Check edge density in circular regions
        circle_edges = 0
        for y in range(height):
            for x in range(width):
                distance = np.sqrt((y - center_y)**2 + (x - center_x)**2)
                if 20 < distance < 80:  # Circular band
                    if edge_array[y, x] > 50:
                        circle_edges += 1
        
        return int(circle_edges / 100)  # Normalize
    
    def _classify_pattern(self, edge_density: float, horizontal: int, vertical: int, circles: int) -> str:
        """Classify the pattern type based on analysis"""
        if edge_density < 0.1:
            return 'plain'
        elif horizontal > 5 or vertical > 5:
            if horizontal > 5 and vertical > 5:
                return 'checkered'
            elif horizontal > 5:
                return 'striped_horizontal'
            else:
                return 'striped_vertical'
        elif circles > 3:
            return 'polka_dot'
        elif edge_density > 0.3:
            return 'complex_pattern'
        else:
            return 'textured'
    
    def _calculate_complexity(self, edge_array: np.ndarray) -> float:
        """Calculate pattern complexity score"""
        edge_density = np.mean(edge_array > 50)
        edge_variance = np.var(edge_array)
        return round(edge_density * edge_variance / 1000, 3)
    
    def analyze_wardrobe_collection(self, collection_name: str, image_field: str = 'image_url') -> Dict[str, any]:
        """
        Analyze all images in a Firestore collection
        
        Args:
            collection_name (str): Name of the Firestore collection
            image_field (str): Field name containing image URLs
            
        Returns:
            dict: Analysis results for the collection
        """
        try:
            # Initialize Firestore client
            db = firestore.Client()
            collection_ref = db.collection(collection_name)
            
            # Get all documents
            docs = collection_ref.stream()
            
            collection_analysis = {
                'total_items': 0,
                'analyzed_items': 0,
                'color_analysis': defaultdict(list),
                'pattern_analysis': defaultdict(list),
                'item_details': []
            }
            
            logger.info(f"Analyzing collection: {collection_name}")
            
            for doc in docs:
                collection_analysis['total_items'] += 1
                data = doc.to_dict()
                
                if image_field in data and data[image_field]:
                    image_url = data[image_field]
                    
                    # For now, we'll analyze local files or download URLs
                    # You might need to implement URL downloading logic
                    if os.path.exists(image_url) or image_url.startswith('http'):
                        try:
                            # Analyze colors and patterns
                            color_result = self.analyze_image_colors(image_url)
                            pattern_result = self.analyze_image_patterns(image_url)
                            
                            if color_result and pattern_result:
                                collection_analysis['analyzed_items'] += 1
                                
                                # Store analysis results
                                item_analysis = {
                                    'doc_id': doc.id,
                                    'brand': data.get('brand_name', 'unknown'),
                                    'colors': color_result,
                                    'patterns': pattern_result
                                }
                                
                                collection_analysis['item_details'].append(item_analysis)
                                
                                # Aggregate color and pattern data
                                if 'primary_color' in color_result:
                                    collection_analysis['color_analysis'][color_result['primary_color']].append(doc.id)
                                
                                if 'pattern_type' in pattern_result:
                                    collection_analysis['pattern_analysis'][pattern_result['pattern_type']].append(doc.id)
                                
                        except Exception as e:
                            logger.warning(f"Failed to analyze image {image_url}: {e}")
            
            # Calculate summary statistics
            collection_analysis['color_summary'] = self._calculate_color_summary(collection_analysis['color_analysis'])
            collection_analysis['pattern_summary'] = self._calculate_pattern_summary(collection_analysis['pattern_analysis'])
            
            return collection_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing collection: {e}")
            return {}
    
    def _calculate_color_summary(self, color_analysis: Dict[str, List]) -> Dict[str, int]:
        """Calculate color distribution summary"""
        return {color: len(items) for color, items in color_analysis.items()}
    
    def _calculate_pattern_summary(self, pattern_analysis: Dict[str, List]) -> Dict[str, int]:
        """Calculate pattern distribution summary"""
        return {pattern: len(items) for pattern, items in pattern_analysis.items()}

def main():
    """Main function to run the wardrobe image analysis"""
    logger.info("=== Wardrobe Image Analyzer ===\n")
    
    # Initialize analyzer
    analyzer = WardrobeImageAnalyzer()
    
    # Get collection name from user
    collection_name = input("Enter Firestore collection name: ").strip()
    
    if not collection_name:
        logger.error("Collection name is required!")
        return
    
    # Get image field name
    image_field = input("Enter image field name (default: image_url): ").strip() or 'image_url'
    
    # Analyze collection
    logger.info("Starting analysis...")
    results = analyzer.analyze_wardrobe_collection(collection_name, image_field)
    
    if results:
        # Display results
        logger.info(f"\n=== Analysis Results ===")
        logger.info(f"Total items: {results['total_items']}")
        logger.info(f"Analyzed items: {results['analyzed_items']}")
        
        # Color summary
        logger.info(f"\n=== Color Distribution ===")
        color_summary = results['color_summary']
        sorted_colors = sorted(color_summary.items(), key=lambda x: x[1], reverse=True)
        for color, count in sorted_colors:
            logger.info(f"{color}: {count} items")
        
        # Pattern summary
        logger.info(f"\n=== Pattern Distribution ===")
        pattern_summary = results['pattern_summary']
        sorted_patterns = sorted(pattern_summary.items(), key=lambda x: x[1], reverse=True)
        for pattern, count in sorted_patterns:
            logger.info(f"{pattern}: {count} items")
        
        # Save detailed results
        output_file = f"wardrobe_analysis_{collection_name}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"\nDetailed results saved to: {output_file}")
        
    else:
        logger.error("No results found or an error occurred.")

if __name__ == "__main__":
    main()
