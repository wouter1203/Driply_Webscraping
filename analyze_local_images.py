#!/usr/bin/env python3
"""
Script to analyze local wardrobe images for colors and patterns
"""

import json
import os
from collections import Counter, defaultdict
from typing import Dict, List, Tuple
import numpy as np
from PIL import Image, ImageFilter
import colorsys
from loguru import logger

class LocalImageAnalyzer:
    """Analyzes local wardrobe images for colors and patterns"""
    
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
    
    def analyze_directory(self, directory_path: str) -> Dict[str, any]:
        """
        Analyze all images in a directory
        
        Args:
            directory_path (str): Path to directory containing images
            
        Returns:
            dict: Analysis results for all images
        """
        # Supported image formats
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
        
        analysis_results = {
            'total_images': 0,
            'analyzed_images': 0,
            'color_summary': defaultdict(int),
            'pattern_summary': defaultdict(int),
            'image_details': []
        }
        
        logger.info(f"Analyzing images in directory: {directory_path}")
        
        # Get all image files
        image_files = []
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    image_files.append(os.path.join(root, file))
        
        analysis_results['total_images'] = len(image_files)
        logger.info(f"Found {len(image_files)} image files")
        
        # Analyze each image
        for image_path in image_files:
            try:
                logger.info(f"Analyzing: {os.path.basename(image_path)}")
                
                # Analyze colors and patterns
                color_result = self.analyze_image_colors(image_path)
                pattern_result = self.analyze_image_patterns(image_path)
                
                if color_result and pattern_result:
                    analysis_results['analyzed_images'] += 1
                    
                    # Store analysis results
                    image_analysis = {
                        'filename': os.path.basename(image_path),
                        'filepath': image_path,
                        'colors': color_result,
                        'patterns': pattern_result
                    }
                    
                    analysis_results['image_details'].append(image_analysis)
                    
                    # Aggregate color and pattern data
                    if 'primary_color' in color_result:
                        analysis_results['color_summary'][color_result['primary_color']] += 1
                    
                    if 'pattern_type' in pattern_result:
                        analysis_results['pattern_summary'][pattern_result['pattern_type']] += 1
                
            except Exception as e:
                logger.warning(f"Failed to analyze image {image_path}: {e}")
        
        # Convert defaultdict to regular dict for JSON serialization
        analysis_results['color_summary'] = dict(analysis_results['color_summary'])
        analysis_results['pattern_summary'] = dict(analysis_results['pattern_summary'])
        
        return analysis_results

def main():
    """Main function to run the local image analysis"""
    logger.info("=== Local Wardrobe Image Analyzer ===\n")
    
    # Initialize analyzer
    analyzer = LocalImageAnalyzer()
    
    # Get directory path from user
    directory_path = input("Enter directory path containing images: ").strip()
    
    if not directory_path:
        logger.error("Directory path is required!")
        return
    
    if not os.path.exists(directory_path):
        logger.error(f"Directory does not exist: {directory_path}")
        return
    
    if not os.path.isdir(directory_path):
        logger.error(f"Path is not a directory: {directory_path}")
        return
    
    # Analyze directory
    logger.info("Starting analysis...")
    results = analyzer.analyze_directory(directory_path)
    
    if results:
        # Display results
        logger.info(f"\n=== Analysis Results ===")
        logger.info(f"Total images found: {results['total_images']}")
        logger.info(f"Successfully analyzed: {results['analyzed_images']}")
        
        # Color summary
        logger.info(f"\n=== Color Distribution ===")
        color_summary = results['color_summary']
        sorted_colors = sorted(color_summary.items(), key=lambda x: x[1], reverse=True)
        for color, count in sorted_colors:
            logger.info(f"{color}: {count} images")
        
        # Pattern summary
        logger.info(f"\n=== Pattern Distribution ===")
        pattern_summary = results['pattern_summary']
        sorted_patterns = sorted(pattern_summary.items(), key=lambda x: x[1], reverse=True)
        for pattern, count in sorted_patterns:
            logger.info(f"{pattern}: {count} images")
        
        # Save detailed results
        output_file = f"local_image_analysis_{os.path.basename(directory_path)}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"\nDetailed results saved to: {output_file}")
        
        # Show some example analyses
        if results['image_details']:
            logger.info(f"\n=== Sample Analysis ===")
            sample = results['image_details'][0]
            logger.info(f"Sample image: {sample['filename']}")
            logger.info(f"Primary color: {sample['colors']['primary_color']}")
            logger.info(f"Pattern type: {sample['patterns']['pattern_type']}")
            logger.info(f"Dominant colors: {sample['colors']['dominant_colors']}")
        
    else:
        logger.error("No results found or an error occurred.")

if __name__ == "__main__":
    main()
