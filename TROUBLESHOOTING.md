# Document Upload Troubleshooting Guide

## Common Issues and Solutions

### Issue: Upload Hangs at 90%

**Symptoms:**
- Frontend progress bar stops at 90%
- No error message displayed
- Backend may or may not show errors

**Diagnosis Steps:**

1. **Check Backend Logs:**
   ```bash
   # Look for these log messages in your uvicorn terminal:
   - "Starting upload for file: ..."
   - "Processing document: ..."
   - "Created X chunks from document"
   - "Generating embeddings..."
   - "Created X chunk records"
   - "Document X processed successfully"
   ```

2. **Check Browser Console (F12 > Console):**
   - Look for JavaScript errors
   - Check for network errors

3. **Check Network Tab (F12 > Network):**
   - Find the POST request to `/api/documents/upload`
   - Check the response status code
   - Check the response body for error messages

**Common Causes:**

1. **Embedding Generation Timeout:**
   - Solution: Embeddings now use fast fallback method
   - Check logs for "Embedding generation error"

2. **Database Commit Issues:**
   - Solution: Added batch commits and rollback handling
   - Check logs for database errors

3. **File Processing Errors:**
   - Solution: Added comprehensive error handling
   - Check logs for "Error processing document"

4. **Missing Uploads Directory:**
   - Solution: Directory is auto-created
   - Check that `backend/uploads/` exists

## Recent Fixes Applied

1. **Embedding Service:**
   - Changed from per-item commits to batch commits
   - Added fallback embedding generation
   - Removed dependency on OpenRouter for embeddings (uses fast hash-based method)

2. **Document Processing:**
   - Added comprehensive logging at each step
   - Improved error handling with rollback
   - Added validation for all steps
   - Fixed embedding count mismatches

3. **Frontend Progress:**
   - Changed progress simulation to stop at 85% and wait for actual completion
   - Improved error messages

4. **Backend Logging:**
   - Added detailed logging throughout the upload process
   - Errors are now logged with full stack traces

## Testing

1. **Test with Small File (< 1MB):**
   ```bash
   # Create a test file
   echo "This is a test document for the HR AI Platform." > test.txt
   ```

2. **Monitor Backend Logs:**
   ```bash
   # Run backend with verbose logging
   uvicorn app.main:app --reload --log-level info
   ```

3. **Check Upload Directory:**
   ```bash
   # Verify uploads directory exists
   ls -la backend/uploads/
   ```

## Error Messages Reference

- "Failed to create text chunks from document" - Text extraction or chunking failed
- "All text chunks are empty" - Extracted text is empty or whitespace only
- "Failed to generate embeddings" - Embedding generation failed (should use fallback)
- "Embedding count mismatch" - Number of embeddings doesn't match chunks (auto-fixed)
- "No valid chunks were created" - All chunks were filtered out as empty

## Performance Notes

- Embedding generation is now fast (hash-based, no API calls)
- Batch database commits improve performance
- Large files may take longer to process (text extraction + chunking)
