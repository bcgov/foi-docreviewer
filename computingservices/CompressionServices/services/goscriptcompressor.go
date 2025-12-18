package services

import (
	"bytes"
	"compressionservices/models"
	"compressionservices/utils"
	"fmt"
	"image"
	"image/jpeg"
	"image/png"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/nfnt/resize"
	"github.com/pdfcpu/pdfcpu/pkg/api"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu/types"

	"github.com/shirou/gopsutil/cpu"
	"github.com/shirou/gopsutil/mem"
)

// func resizeImage1(inputImageData []byte) ([]byte, error) {
// 	// Detect image type
// 	img, format, err := image.Decode(bytes.NewReader(inputImageData))
// 	if err != nil {
// 		return nil, fmt.Errorf("failed to decode image: %v", err)
// 	}
// 	// Resize the image
// 	imgResized := resize.Resize(800, 0, img, resize.Lanczos3)
// 	// Encode resized image back to bytes
// 	var buf bytes.Buffer
// 	switch strings.ToLower(format) {
// 	case "jpeg", "jpg":
// 		err = jpeg.Encode(&buf, imgResized, nil)
// 	case "png":
// 		err = png.Encode(&buf, imgResized)
// 	default:
// 		return nil, fmt.Errorf("unsupported image format: %s", format)
// 	}
// 	if err != nil {
// 		return nil, fmt.Errorf("failed to encode resized image: %v", err)
// 	}
// 	fmt.Println("Image successfully resized.")
// 	return buf.Bytes(), nil
// }

func resizeImage(inputPath string) ([]byte, error, bool) {
	skipCompression := false
	// Open the file
	file, err := os.Open(inputPath)
	if err != nil {
		return nil, fmt.Errorf("failed to open image file: %v", err), skipCompression
	}
	defer file.Close()
	fmt.Println("inputPath:", inputPath)
	// Decode the image and detect format
	img, format, err := image.Decode(file)
	if err != nil {
		return nil, fmt.Errorf("failed to decode image: %v", err), skipCompression
	}
	// Resize the image (800px width, preserve aspect ratio)
	imgResized := resize.Resize(800, 0, img, resize.Lanczos3)
	// Create a temp file for the resized image
	outputFile, err := os.CreateTemp("", "resized_*.img")
	if err != nil {
		return nil, fmt.Errorf("failed to create temp output file: %v", err), skipCompression
	}
	defer func() {
		_ = outputFile.Close()
		_ = os.Remove(outputFile.Name())
	}()
	// Encode the resized image to the temp file
	switch strings.ToLower(format) {
	case "jpeg", "jpg":
		err = jpeg.Encode(outputFile, imgResized, nil)
	case "png":
		err = png.Encode(outputFile, imgResized)
	default:
		return nil, fmt.Errorf("unsupported image format: %s", format), skipCompression
	}
	if err != nil {
		return nil, fmt.Errorf("failed to encode resized image: %v", err), skipCompression
	}
	// Read resized image from file
	resizedData, err := os.ReadFile(outputFile.Name())
	if err != nil {
		return nil, fmt.Errorf("failed to read resized image: %v", err), skipCompression
	}
	fmt.Println("Image successfully resized.")
	return resizedData, nil, skipCompression
}

// Function to log current memory usage
func getMemoryUsage() uint64 {
	v, err := mem.VirtualMemory()
	if err != nil {
		log.Fatalf("Error getting memory usage: %v", err)
	}
	return v.Used
}

// Function to log current CPU usage percentage
func getCPUUsage() float64 {
	percent, err := cpu.Percent(0, false) // Get CPU usage percentage (0 - global)
	if err != nil {
		log.Fatalf("Error getting CPU usage: %v", err)
	}
	return percent[0]
}

// Fallback detection - can be used if pdfcpu is not able to validate pdf or with memory issues
func detectJBIG2ImagesWithStreamingBytes(path string) (bool, error) {
	const needle = "/JBIG2Decode"
	const bufSize = 64 * 1024

	file, err := os.Open(path)
	if err != nil {
		return false, err
	}
	defer file.Close()

	needleBytes := []byte(needle)
	overlap := len(needleBytes) - 1

	buf := make([]byte, bufSize)
	var prev []byte

	for {
		n, err := file.Read(buf)
		if n > 0 {
			chunk := buf[:n]

			// Prepend overlap from previous chunk
			if len(prev) > 0 {
				combined := append(prev, chunk...)
				if bytes.Contains(combined, needleBytes) {
					return true, nil
				}

				// Keep last overlap bytes
				if len(combined) >= overlap {
					prev = append([]byte{}, combined[len(combined)-overlap:]...)
				} else {
					prev = append([]byte{}, combined...)
				}
			} else {
				if bytes.Contains(chunk, needleBytes) {
					return true, nil
				}

				if len(chunk) >= overlap {
					prev = append([]byte{}, chunk[len(chunk)-overlap:]...)
				} else {
					prev = append([]byte{}, chunk...)
				}
			}
		}

		if err == io.EOF {
			break
		}
		if err != nil {
			return false, err
		}
	}

	return false, nil
}

func detectJBIG2ImagesWithPdfcpu(inputTempFile string) (bool, error) {
	ctx, err := api.ReadContextFile(inputTempFile)
	if err != nil {
		return false, err
	}

	// Iterate all objects in the PDF
	for objNum, entry := range ctx.XRefTable.Table {
		if entry.Free {
			continue // entry.Free is an unused object
		}

		obj := entry.Object
		streamDict, ok := obj.(types.StreamDict)
		if !ok {
			continue
		}

		if streamDict.Subtype() == nil || *streamDict.Subtype() != "Image" {
			continue
		}

		// Check filters from FilterPipeline for JBIG2 - this should catch all normal uses of JBIG2 encoding
		filters := streamDict.FilterPipeline
		for _, f := range filters {
			if f.Name == "JBIG2Decode" {
				fmt.Printf("JBIG2 image found in object %d\n", objNum)
				return true, nil
			}
		}
	}

	return false, nil
}

// Function to compress the PDF
func compressPDF(inputTempFile string) ([]byte, error, bool) {
	var hasjbig2encoding bool
	const maxPdfcpuSize = 500 << 20 // 500 MB

	fileInfo, err := os.Stat(inputTempFile)
	if err != nil {
		return nil, err, false
	}

	if fileInfo.Size() > maxPdfcpuSize { // Skip using pdfcpu for large files
		hasjbig2encoding, err = detectJBIG2ImagesWithStreamingBytes(inputTempFile)
		if err != nil {
			return nil, fmt.Errorf("failed during jbig2 byte detection: %v", err), false
		}
	} else {
		// Handle rare cases where pdfcpu panics
		hasjbig2encoding, err = func() (bool, error) {
			defer func() {
				if r := recover(); r != nil {
					err = fmt.Errorf("pdfcpu panic: %v", r)
				}
			}()
			return detectJBIG2ImagesWithPdfcpu(inputTempFile)
		}()

		if err != nil {
			fmt.Println("JBIG2 encoding detection with pdfcpu failed, falling back to bytes-based detection")
			hasjbig2encoding, err = detectJBIG2ImagesWithStreamingBytes(inputTempFile)
			if err != nil {
				return nil, fmt.Errorf("failed during jbig2 encoding detection: %v", err), false
			}
		}
	}
	skipCompression := false

	if hasjbig2encoding {
		fmt.Println("Has jbig2 encoding, skipping compression")
		skipCompression = true
		return nil, nil, skipCompression
	}

	gsTmpDir, err := os.MkdirTemp("", "gs_work_*")
	if err != nil {
		return nil, fmt.Errorf("failed to create temp dir: %v", err), skipCompression
	}
	// Clean up everything in this dir at the end
	defer os.RemoveAll(gsTmpDir)
	// Create output file inside this dir
	outputTempFile, err := os.CreateTemp(gsTmpDir, "output_*.pdf")
	if err != nil {
		return nil, fmt.Errorf("failed to create temp output file: %v", err), skipCompression
	}
	//defer os.Remove(outputTempFile.Name())
	defer outputTempFile.Close()
	// Ghostscript command to compress the PDF
	var stderr bytes.Buffer
	cmd := exec.Command(
		"gs",
		//"gswin64c", // Ghostscript command --- gs
		"-sDEVICE=pdfwrite",
		"-dCompatibilityLevel=1.4",
		"-dPDFSETTINGS=/ebook",
		"-dNOPAUSE",
		"-dQUIET",
		"-dBATCH",
		"-dOptimize=true",
		"-dSubsetFonts=true", // Subset fonts to only include the characters used in the document
		"-dDownsampleColorImages=true",
		"-dDownsampleGrayImages=true",
		"-dColorImageResolution=150", // Downsample color images to 150 DPI
		"-dGrayImageResolution=150",  // Downsample grayscale images to 150 DPI
		"-dRemoveAllUnusedObjects=true",
		"-dDetectDuplicateImages=true", // Detect and eliminate duplicate images
		"-sOutputFile="+outputTempFile.Name(),
		inputTempFile,
	)
	// Set up command's stderr to capture output
	cmd.Stderr = &stderr
	// Force Ghostscript to use our temp dir for its intermediates
	cmd.Env = append(os.Environ(), "TMPDIR="+gsTmpDir)
	err = cmd.Run()
	if err != nil {
		return nil, fmt.Errorf("ghostscript error: %v\nStderr: %s", err, stderr.String()), skipCompression
	}
	// Check if the output file was created
	if _, err := os.Stat(outputTempFile.Name()); os.IsNotExist(err) {
		return nil, fmt.Errorf("ghostscript did not create output file: %v", err), skipCompression
	}
	// Read the compressed file data from the output file
	compressedFileData, err := os.ReadFile(outputTempFile.Name())
	if err != nil {
		return nil, fmt.Errorf("failed to read compressed file: %w", err), false
	}
	// Check if output file size is smaller than original
	compressedFileInfo, err := os.Stat(outputTempFile.Name())
	if err != nil {
		return nil, fmt.Errorf("failed to stat compressed file: %w", err), false
	}
	originalFileInfo, err := os.Stat(inputTempFile) // use the string path directly
	if err != nil {
		return nil, fmt.Errorf("failed to stat original file: %w", err), false
	}
	var compressionRatio float64
	if originalFileInfo.Size() > 0 {
		compressionRatio = float64(compressedFileInfo.Size()) / float64(originalFileInfo.Size())
	} else {
		compressionRatio = 0
	}
	if compressionRatio > 0.9 {
		fmt.Println("Compression ratio too high, skipping compression")
		skipCompression = true
		return nil, nil, skipCompression
	}
	if len(compressedFileData) == 0 {
		return nil, fmt.Errorf("compressed file is empty, Ghostscript may have failed to process"), skipCompression
	}
	return compressedFileData, nil, skipCompression
}

func processFileFromPresignedUrl(inputUrl string, bucket string, key string, s3cred *models.S3Credentials) (string, int, string, error, bool) {

	accessKey := s3cred.S3AccessKey
	secretKey := s3cred.S3SecretKey
	// Extract filename from the URL
	urlParts := strings.Split(key, "/")
	if len(urlParts) == 0 {
		return "", 0, "", fmt.Errorf("invalid URL format: %s", key), false
	}
	filenameWithParams := urlParts[len(urlParts)-1]
	filename := strings.Split(filenameWithParams, "?")[0]
	ext := strings.ToLower(filepath.Ext(filename))
	var cleanup func()
	// Step 1: Download file from presigned URL
	inputTempFile, cleanup, err := downloadFile(inputUrl, ext)
	if err != nil {
		return "", 0, "", fmt.Errorf("failed to download file: %v", err), false
	}
	// Defer cleanup safely
	if cleanup != nil {
		defer cleanup()
	}
	// Step 2: Compress the downloaded PDF
	compressedPdfData, error, skipCompression := processFile(inputTempFile, ext)
	if error != nil {
		return "", 0, "", fmt.Errorf("failed to compress file: %v", error), skipCompression
	}
	if skipCompression {
		return "", 0, ext, nil, skipCompression
	}
	expiration := 15 * time.Minute
	// Step 3: Upload the compressed file back to S3
	presignedURL, err := generatePresignedUploadURL(utils.ViperEnvVariable("COMPRESSION_S3_HOST"), accessKey, secretKey, bucket, key,
		utils.ViperEnvVariable("COMPRESSION_S3_REGION"), expiration)
	if err != nil {
		fmt.Println("Error generating presigned URL:", err)
		return "", 0, "", fmt.Errorf("failed to compress file: %v", err), skipCompression
	}
	err = uploadUsingPresignedURL(presignedURL, compressedPdfData)
	if err != nil {
		return "", 0, "", fmt.Errorf("failed to upload compressed file to S3: %v", err), skipCompression
	}
	compressedFileSize := len(compressedPdfData)
	fmt.Printf("File successfully compressed with file size: %d bytes\n", compressedFileSize)
	return presignedURL, compressedFileSize, ext, nil, skipCompression
}

func uploadUsingPresignedURL(presignedURL string, fileData []byte) error {
	// Create the HTTP PUT request with the file data
	req, err := http.NewRequest("PUT", presignedURL, bytes.NewReader(fileData))
	if err != nil {
		return fmt.Errorf("failed to create request: %v", err)
	}
	// Perform the upload request
	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("failed to upload to S3 using presigned URL: %v", err)
	}
	defer resp.Body.Close()
	// Check the response status
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("upload failed with status %d: %s", resp.StatusCode, string(body))
	}
	return nil
}

func downloadFile(url string, ext string) (string, func(), error) {
	fmt.Println("Inside downloadFile")
	noOpCleanup := func() {}
	resp, err := http.Get(url)
	if err != nil {
		return "", noOpCleanup, fmt.Errorf("failed to download file: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return "", noOpCleanup, fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}
	// Create a dedicated temp directory for this download
	tmpDir, err := os.MkdirTemp("", "download_work_*")
	if err != nil {
		return "", noOpCleanup, fmt.Errorf("failed to create temp dir: %v", err)
	}
	// Write to temp file
	// //tmpFile, err := os.CreateTemp("", "downloaded_*.pdf")
	tmpFile, err := os.CreateTemp(tmpDir, fmt.Sprintf("downloaded_*%s", ext))
	if err != nil {
		// clean temp dir on error
		os.RemoveAll(tmpDir)
		return "", noOpCleanup, fmt.Errorf("failed to create temp file: %v", err)
	}
	//defer tmpFile.Close()
	_, err = io.Copy(tmpFile, resp.Body)
	if err != nil {
		return "", noOpCleanup, fmt.Errorf("failed to write response to temp file: %v", err)
	}
	// Cleanup function to call after using the file
	cleanup := func() {
		_ = os.RemoveAll(tmpDir)
	}
	return tmpFile.Name(), cleanup, nil
}

// func downloadFile1(url string) ([]byte, error) {
// 	fmt.Println("Inside downloadFile")
// 	resp, err := http.Get(url)
// 	fmt.Println("resp", resp)
// 	if err != nil {
// 		return nil, fmt.Errorf("failed to download file: %v", err)
// 	}
// 	defer resp.Body.Close()

// 	fileData, err := io.ReadAll(resp.Body)
// 	fmt.Println("fileData", fileData)
// 	if err != nil {
// 		return nil, fmt.Errorf("failed to read downloaded file: %v", err)
// 	}
// 	return fileData, nil
// }

// processFile handles different types of files (PDF, JPG, PNG)
func processFile(inputTempFile string, ext string) ([]byte, error, bool) {
	switch ext {
	case ".pdf":
		// return processPDF(inputFile, outputFile)
		return processPDF(inputTempFile)
	case ".jpg", ".png", ".jpeg":
		// return processImage(inputFile, outputFile)
		return processImage(inputTempFile)
	default:
		// If the file is neither PDF nor image, skip processing
		return nil, fmt.Errorf("file cannot be compressed as it is neither PDF nor image"), false
	}
}

// processPDF handles PDF compression based on file name length
func processPDF(inputTempFile string) ([]byte, error, bool) {
	// if len(outputFile) > 250 {
	// 	return compressLengthyNamePDF(inputFile, outputFile)
	// }
	return compressPDF(inputTempFile)
}

// processImage handles image resizing
func processImage(inputTempFile string) ([]byte, error, bool) {
	return resizeImage(inputTempFile)
}

func StartCompression(message *models.CompressionProducerMessage) (string, int, string, bool, error, bool) {

	folderPath, s3cred, bucketname, err := GetFilefroms3(message)
	if err != nil {
		fmt.Printf("Error in GetFilefroms3 method: %v\n", err)
		return "", 0, "", true, err, false // Return error flag as true if this step fails
	}
	// Define S3 path
	bucketName := "/" + bucketname + "/"
	objectKey := message.S3FilePath
	// Record start time and measure initial resource usage
	startTime := time.Now()
	//initialCPU := getCPUUsage()
	//initialMemory := getMemoryUsage()
	//fmt.Printf("Initial CPU Usage: %.2f%%\n", initialCPU)
	//fmt.Printf("Initial Memory Usage: %d MB\n", initialMemory/(1024*1024))
	// Start the compression process
	fmt.Println("Starting file compression...")
	// Process the file from the presigned URL and get the compressed file size
	presignedUrl, compressedFileSize, extension, error, skipCompression := processFileFromPresignedUrl(folderPath, bucketName, objectKey, s3cred)
	if error != nil {
		fmt.Printf("Error in processing file from presigned URL: %v\n", error)
		return "", 0, "", true, error, skipCompression // Return error flag as true if this step fails
	}
	// Clean up the URL to remove query params if present
	s3FilePath := presignedUrl
	if idx := strings.Index(presignedUrl, "?"); idx != -1 {
		s3FilePath = presignedUrl[:idx]
	}
	//fmt.Println("s3FilePath URL:", s3FilePath)
	// Record end time and calculate the time taken for compression
	duration := time.Since(startTime)
	//finalCPU := getCPUUsage()
	//finalMemory := getMemoryUsage()
	// Log the resource usage and time taken
	// fmt.Printf("Final CPU Usage: %.2f%%\n", finalCPU)
	// fmt.Printf("Final Memory Usage: %d MB\n", finalMemory/(1024*1024))
	//fmt.Printf("Time taken for compression: %v\n", duration)
	// Calculate and log the differences in resource usage
	//cpuDifference := finalCPU - initialCPU
	//memoryDifference := finalMemory - initialMemory
	// fmt.Printf("CPU Usage during compression: %.2f%%\n", cpuDifference)
	// fmt.Printf("Memory Used during compression: %d MB\n", memoryDifference/(1024*1024))
	// Success message
	fmt.Printf("saved compressed file & time taken for compression:%v\n", duration)
	// Return the S3 file path, compressed size, and the error flag
	return s3FilePath, compressedFileSize, extension, false, nil, skipCompression
}

// func compressLengthyNamePDF(inputPdfPath string, outputPdfPath string) error {
// 	tempFileName := fmt.Sprintf("temp_file_%d.pdf", time.Now().UnixNano())
// 	tempFilePath := filepath.Join("C:/codebase/doc_compress/Files/HTH-2024-40538/HTH-2024-40538_Compressed/HTH-2024-40538_GO_GHOSTSCRIPT/", tempFileName)
// 	// Create the temporary file
// 	tempFile, err := os.Create(tempFilePath)
// 	if err != nil {
// 		return fmt.Errorf("failed to create temporary file: %v", err)
// 	}
// 	defer tempFile.Close()
// 	err = compressPDF(inputPdfPath, tempFilePath)
// 	tempFile.Close() // Ensure the file is closed after writing
// 	// Check if the file exists before attempting to rename it
// 	_, err = os.Stat(tempFilePath)
// 	if os.IsNotExist(err) {
// 		return fmt.Errorf("temporary file does not exist: %v", tempFilePath)
// 	}
// 	// Rename the temporary output file to the final file name
// 	err = os.Rename(tempFilePath, outputPdfPath)
// 	if err != nil {
// 		return fmt.Errorf("failed to rename temp file to final output file: %v", err)
// 	}
// 	// Successfully renamed the output file
// 	fmt.Println("Output file renamed to:", outputPdfPath)
// 	return nil
// }
