# 🔍 Driply Duplicate Detection System

This system automatically detects and handles duplicate images in your Firestore wardrobe collection using perceptual image hashing and similarity analysis.

## 🚀 Features

- **Automatic Duplicate Detection**: Uses perceptual hashing to identify exact duplicates
- **Similar Image Detection**: Finds images that are very similar but not exact duplicates
- **Safe Detection Mode**: Read-only mode to identify duplicates without removing them
- **Automatic Cleanup**: Remove duplicates with configurable strategies
- **Detailed Reporting**: Generate comprehensive reports of all findings
- **Firestore Integration**: Works directly with your existing Firestore setup

## 📋 Prerequisites

1. **Google Cloud Credentials**: Ensure you have proper authentication set up
2. **Dependencies**: Install required packages (see Installation section)
3. **Firestore Access**: Your application must have read/write access to the collection

## 🛠️ Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Verify Google Cloud Setup**:
   ```bash
   # Make sure you're authenticated
   gcloud auth application-default login
   
   # Or set environment variable
   export GOOGLE_APPLICATION_CREDENTIALS="path/to/your/service-account-key.json"
   ```

## 🎯 Usage

### Quick Start - Safe Detection

To safely detect duplicates without making any changes:

```bash
python run_duplicate_detection.py --detect
```

This will:
- Scan your entire wardrobe collection
- Download and analyze all images
- Generate a detailed report
- Save results to `wardrobe_duplicates_wardrobe.txt`

### Remove Duplicates

To detect and remove duplicates (with confirmation):

```bash
python run_duplicate_detection.py --remove
```

This will:
- Detect all duplicates
- Show you exactly what will be removed
- Ask for confirmation before proceeding
- Remove duplicates and generate cleanup report

### Advanced Usage

#### Custom Collection Name
```bash
python run_duplicate_detection.py --detect --collection test_wardrobe
```

#### Adjust Similarity Threshold
```bash
# Lower threshold = more sensitive to differences
python run_duplicate_detection.py --detect --threshold 0.90

# Higher threshold = only exact matches
python run_duplicate_detection.py --detect --threshold 0.98
```

#### Different Removal Strategies
```bash
# Keep the first document in each duplicate group
python run_duplicate_detection.py --remove --strategy keep_first

# Keep the last document in each duplicate group  
python run_duplicate_detection.py --remove --strategy keep_oldest

# Keep the first document (default)
python run_duplicate_detection.py --remove --strategy keep_newest
```

## 🔧 How It Works

### 1. Image Hashing
- Downloads each image from your Firestore collection
- Converts to grayscale and resizes to 8x8 pixels
- Calculates perceptual hash based on pixel intensity patterns
- Creates a 64-bit hash that represents the image content

### 2. Duplicate Detection
- Groups documents by identical image hashes
- Identifies groups with multiple documents as duplicates
- Calculates similarity between different hashes for near-duplicates

### 3. Similarity Analysis
- Compares all image pairs using Hamming distance
- Identifies images above your similarity threshold
- Helps catch duplicates that might have slight variations

### 4. Cleanup Strategies
- **keep_newest**: Keeps the first document in each group
- **keep_oldest**: Keeps the last document in each group  
- **keep_first**: Keeps the first document in each group

## 📊 Output Files

### Detection Report (`wardrobe_duplicates_[collection].txt`)
- List of all duplicate groups
- Document details for each duplicate
- Similarity analysis results
- Recommendations for cleanup

### Cleanup Report (`wardrobe_after_cleanup_[collection].txt`)
- Summary of removed documents
- Remaining duplicates (if any)
- Error logs from cleanup process

## ⚠️ Important Notes

### Safety Features
- **Always run with `--detect` first** to see what will be affected
- **Interactive confirmation** required before any deletions
- **Detailed logging** of all operations
- **Automatic backup** of removal results

### Performance Considerations
- **Large collections** may take significant time to process
- **Image downloads** are cached in temporary directory
- **Memory usage** scales with collection size
- **Network bandwidth** required for image downloads

### Error Handling
- **Graceful failures** for individual images
- **Detailed error logging** for troubleshooting
- **Continues processing** even if some images fail
- **Rollback not available** - deletions are permanent

## 🚨 Troubleshooting

### Common Issues

#### Authentication Errors
```bash
# Check your credentials
gcloud auth list
gcloud config list

# Set application default credentials
gcloud auth application-default login
```

#### Collection Not Found
```bash
# Verify collection name
python run_duplicate_detection.py --detect --collection correct_collection_name
```

#### Image Download Failures
- Check network connectivity
- Verify image URLs are accessible
- Some images may be private or expired

#### Memory Issues
- Process smaller collections in batches
- Ensure sufficient disk space for temporary files
- Close other applications to free memory

### Debug Mode
For detailed logging, you can modify the script to increase log verbosity:

```python
# In duplicate_detector.py, change log level
logger.add(lambda msg: print(msg, end=""), format="<level>{level}</level> | {message}\n", colorize=True, level="DEBUG")
```

## 🔄 Regular Maintenance

### Recommended Workflow
1. **Weekly**: Run detection to identify new duplicates
2. **Monthly**: Perform cleanup to remove accumulated duplicates
3. **After major imports**: Always check for duplicates

### Automation
You can set up automated duplicate detection:

```bash
# Add to crontab for weekly detection
0 2 * * 1 cd /path/to/your/project && python run_duplicate_detection.py --detect >> duplicate_detection.log 2>&1
```

## 📈 Performance Tips

### For Large Collections
- **Batch processing**: Process in smaller chunks
- **Parallel processing**: Modify script for concurrent downloads
- **Caching**: Store hashes to avoid re-processing
- **Incremental updates**: Only process new documents

### Optimization
- **Image compression**: Reduce download sizes
- **Hash caching**: Store computed hashes
- **Selective processing**: Skip already-processed images

## 🤝 Contributing

To improve the duplicate detection system:

1. **Fork the repository**
2. **Create a feature branch**
3. **Implement improvements**
4. **Test thoroughly**
5. **Submit pull request**

## 📞 Support

If you encounter issues:

1. **Check the logs** for detailed error messages
2. **Verify your setup** meets all prerequisites
3. **Test with a small collection** first
4. **Review the troubleshooting section**

## 🔮 Future Enhancements

- **Machine Learning**: Better similarity detection
- **Batch Operations**: Process multiple collections
- **Cloud Functions**: Serverless duplicate detection
- **Real-time Monitoring**: Automatic duplicate alerts
- **Image Preprocessing**: Better handling of different formats

---

**Happy duplicate hunting! 🎯**
