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

func resizeImage(inputPath string) ([]byte, error) {
	// Open the file
	file, err := os.Open(inputPath)
	if err != nil {
		return nil, fmt.Errorf("failed to open image file: %v", err)
	}
	defer file.Close()
	fmt.Println("inputPath:", inputPath)

	fmt.Println("file:", file)

	// Decode the image and detect format
	img, format, err := image.Decode(file)
	if err != nil {
		return nil, fmt.Errorf("failed to decode image: %v", err)
	}
	// Resize the image (800px width, preserve aspect ratio)
	imgResized := resize.Resize(800, 0, img, resize.Lanczos3)
	// Create a temp file for the resized image
	outputFile, err := os.CreateTemp("", "resized_*.img")
	if err != nil {
		return nil, fmt.Errorf("failed to create temp output file: %v", err)
	}
	defer os.Remove(outputFile.Name()) // Clean up
	defer outputFile.Close()
	// Encode the resized image to the temp file
	switch strings.ToLower(format) {
	case "jpeg", "jpg":
		err = jpeg.Encode(outputFile, imgResized, nil)
	case "png":
		err = png.Encode(outputFile, imgResized)
	default:
		return nil, fmt.Errorf("unsupported image format: %s", format)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to encode resized image: %v", err)
	}
	// Read resized image from file
	resizedData, err := os.ReadFile(outputFile.Name())
	if err != nil {
		return nil, fmt.Errorf("failed to read resized image: %v", err)
	}
	fmt.Println("Image successfully resized.")
	return resizedData, nil
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

// Function to compress the PDF
func compressPDF(inputTempFile string) ([]byte, error) {
	//fmt.Println("Inside compressPDF function")
	// Write the input file to a temporary file
	// inputTempFile, err := os.CreateTemp("", "input_*.pdf")
	// if err != nil {
	// 	return nil, fmt.Errorf("failed to create temp input file: %v", err)
	// }
	//defer os.Remove(inputTempFile.Name())
	// _, err = inputTempFile.Write(inputPdfData)
	// if err != nil {
	// 	return nil, fmt.Errorf("failed to write temp input file: %v", err)
	// }
	// Log the input temp file path
	//fmt.Printf("Input Temp File: %s\n", inputTempFile.Name())
	// Create the output file for the compressed file
	outputTempFile, err := os.CreateTemp("", "output_*.pdf")
	if err != nil {
		return nil, fmt.Errorf("failed to create temp output file: %v", err)
	}
	defer os.Remove(outputTempFile.Name())
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
	err = cmd.Run()
	if err != nil {
		return nil, fmt.Errorf("ghostscript error: %v\nStderr: %s", err, stderr.String())
	}
	fmt.Println("Command Run executed")

	// Check if the output file was created
	if _, err := os.Stat(outputTempFile.Name()); os.IsNotExist(err) {
		return nil, fmt.Errorf("ghostscript did not create output file: %v", err)
	}
	// Read the compressed file data from the output file
	compressedFileData, err := os.ReadFile(outputTempFile.Name())
	if err != nil {
		return nil, fmt.Errorf("failed to read compressed file: %v", err)
	}
	if len(compressedFileData) == 0 {
		return nil, fmt.Errorf("compressed file is empty, Ghostscript may have failed to process")
	}
	return compressedFileData, nil
}

func processFileFromPresignedUrl(inputUrl string, bucket string, key string, s3cred *models.S3Credentials) (string, int, string, error) {

	accessKey := s3cred.S3AccessKey
	secretKey := s3cred.S3SecretKey
	// Extract filename from the URL
	urlParts := strings.Split(key, "/")
	if len(urlParts) == 0 {
		return "", 0, "", fmt.Errorf("invalid URL format: %s", key)
	}
	filenameWithParams := urlParts[len(urlParts)-1]
	filename := strings.Split(filenameWithParams, "?")[0]
	//fmt.Println("filename:", filename)
	ext := strings.ToLower(filepath.Ext(filename))
	// Step 1: Download file from presigned URL
	inputTempFile, err := downloadFile(inputUrl, ext)
	if err != nil {
		return "", 0, "", fmt.Errorf("failed to download file: %v", err)
	}
	// Step 2: Compress the downloaded PDF
	compressedPdfData, error := processFile(inputTempFile, ext)
	if error != nil {
		return "", 0, "", fmt.Errorf("failed to compress file: %v", error)
	}
	expiration := 15 * time.Minute
	// Step 3: Upload the compressed file back to S3
	presignedURL, err := generatePresignedUploadURL(utils.ViperEnvVariable("COMPRESSION_S3_HOST"), accessKey, secretKey, bucket, key,
		utils.ViperEnvVariable("COMPRESSION_S3_REGION"), expiration)
	if err != nil {
		fmt.Println("Error generating presigned URL:", err)
		return "", 0, "", fmt.Errorf("failed to compress file: %v", err)
	}
	err = uploadUsingPresignedURL(presignedURL, compressedPdfData)
	if err != nil {
		return "", 0, "", fmt.Errorf("failed to upload compressed file to S3: %v", err)
	}
	compressedFileSize := len(compressedPdfData)
	fmt.Printf("File successfully compressed with file size: %d bytes\n", compressedFileSize)
	//log.Println("File successfully compressed and uploaded & compressed filesize")
	return presignedURL, compressedFileSize, ext, nil
}

func uploadUsingPresignedURL(presignedURL string, fileData []byte) error {
	//fmt.Println("\npresignedURL-UPLOAD:", presignedURL)
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
	fmt.Println("Successfully uploaded the file using presigned URL.")
	return nil
}

func downloadFile(url string, ext string) (string, error) {
	fmt.Println("Inside downloadFile")
	resp, err := http.Get(url)
	if err != nil {
		return "", fmt.Errorf("failed to download file: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}
	// Write to temp file
	// //tmpFile, err := os.CreateTemp("", "downloaded_*.pdf")
	tmpFile, err := os.CreateTemp("", fmt.Sprintf("downloaded_*%s", ext))
	if err != nil {
		return "", fmt.Errorf("failed to create temp file: %v", err)
	}
	defer tmpFile.Close()
	_, err = io.Copy(tmpFile, resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to write response to temp file: %v", err)
	}
	//fmt.Println("Downloaded to:", tmpFile.Name())
	return tmpFile.Name(), nil
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
func processFile(inputTempFile string, ext string) ([]byte, error) {
	switch ext {
	case ".pdf":
		// return processPDF(inputFile, outputFile)
		return processPDF(inputTempFile)
	case ".jpg", ".png", ".jpeg":
		// return processImage(inputFile, outputFile)
		return processImage(inputTempFile)
	default:
		// If the file is neither PDF nor image, skip processing
		return nil, fmt.Errorf("file cannot be compressed as it is neither PDF nor image")
	}
}

// processPDF handles PDF compression based on file name length
func processPDF(inputTempFile string) ([]byte, error) {
	// if len(outputFile) > 250 {
	// 	return compressLengthyNamePDF(inputFile, outputFile)
	// }
	return compressPDF(inputTempFile)
}

// processImage handles image resizing
func processImage(inputTempFile string) ([]byte, error) {
	return resizeImage(inputTempFile)
}

func StartCompression(message *models.CompressionProducerMessage) (string, int, string, bool, error) {

	folderPath, s3cred, bucketname, err := GetFilefroms3(message)
	if err != nil {
		fmt.Printf("Error in GetFilefroms3 method: %v\n", err)
		return "", 0, "", true, err // Return error flag as true if this step fails
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
	presignedUrl, compressedFileSize, extension, error := processFileFromPresignedUrl(folderPath, bucketName, objectKey, s3cred)
	if error != nil {
		fmt.Printf("Error in processing file from presigned URL: %v\n", error)
		return "", 0, "", true, error // Return error flag as true if this step fails
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
	return s3FilePath, compressedFileSize, extension, false, nil
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
