package services

import (
	"fmt"
	"image"
	"image/jpeg"
	"image/png"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/nfnt/resize"

	"github.com/shirou/gopsutil/cpu"
	"github.com/shirou/gopsutil/mem"
)

// Function to log current CPU usage percentage
func getCPUUsage() float64 {
	percent, err := cpu.Percent(0, false) // Get CPU usage percentage (0 - global)
	if err != nil {
		log.Fatalf("Error getting CPU usage: %v", err)
	}
	return percent[0]
}

// Function to resize an image using bimg
func resizeImage(inputFile, outputFile string) error {
	// Open the input image
	file, err := os.Open(inputFile)
	if err != nil {
		return fmt.Errorf("failed to open input file: %v", err)
	}
	defer file.Close()

	// Decode the image (supports JPEG, PNG, etc.)
	img, _, err := image.Decode(file)
	if err != nil {
		return fmt.Errorf("failed to decode image: %v", err)
	}

	// Resize the image
	imgResized := resize.Resize(800, 0, img, resize.Lanczos3) // Maintains aspect ratio

	// Create the output file
	outFile, err := os.Create(outputFile)
	if err != nil {
		return fmt.Errorf("failed to create output file: %v", err)
	}
	defer outFile.Close()

	// Save the resized image in the correct format (JPEG or PNG)
	switch ext := outputFile[len(outputFile)-3:]; ext {
	case "jpg", "jpeg":
		err = jpeg.Encode(outFile, imgResized, nil)
	case "png":
		err = png.Encode(outFile, imgResized)
	default:
		return fmt.Errorf("unsupported file format: %s", ext)
	}

	if err != nil {
		return fmt.Errorf("failed to save resized image: %v", err)
	}

	fmt.Printf("Image successfully resized and saved to: %s\n", outputFile)
	return nil
}

// Function to log current memory usage
func getMemoryUsage() uint64 {
	v, err := mem.VirtualMemory()
	if err != nil {
		log.Fatalf("Error getting memory usage: %v", err)
	}
	return v.Used
}
func compressPDF(inputPdfPath string, outputPdfPath string) error {
	// Ghostscript command to compress the PDF
	cmd := exec.Command(
		"gswin64c", // Ghostscript command --- gs
		"-sDEVICE=pdfwrite",
		"-dCompatibilityLevel=1.4",
		"-dPDFSETTINGS=/ebook",
		"-dNOPAUSE",
		"-dQUIET",
		"-dBATCH",
		// "-dCompressFonts=true",
		"-dOptimize=true",
		"-dSubsetFonts=true", // Subset fonts to only include the characters used in the document
		"-dDownsampleColorImages=true",
		"-dDownsampleGrayImages=true",
		"-dColorImageResolution=150", // Downsample color images to 150 DPI
		"-dGrayImageResolution=150",  // Downsample grayscale images to 150 DPI
		"-dRemoveAllUnusedObjects=true",
		"-dDetectDuplicateImages=true", // Detect and eliminate duplicate images
		"-sOutputFile="+outputPdfPath,
		inputPdfPath)

	// Run the command to compress the PDF
	err := cmd.Run()
	if err != nil {
		log.Printf("Error running Ghostscript command: %s\n", outputPdfPath)
	}
	return nil
}
func compressLengthyNamePDF(inputPdfPath string, outputPdfPath string) error {
	tempFileName := fmt.Sprintf("temp_file_%d.pdf", time.Now().UnixNano())
	tempFilePath := filepath.Join("C:/codebase/doc_compress/Files/HTH-2024-40538/HTH-2024-40538_Compressed/HTH-2024-40538_GO_GHOSTSCRIPT/", tempFileName)

	// Create the temporary file
	tempFile, err := os.Create(tempFilePath)
	if err != nil {
		return fmt.Errorf("failed to create temporary file: %v", err)
	}
	defer tempFile.Close()

	err = compressPDF(inputPdfPath, tempFilePath)

	tempFile.Close() // Ensure the file is closed after writing

	// Check if the file exists before attempting to rename it
	_, err = os.Stat(tempFilePath)
	if os.IsNotExist(err) {
		return fmt.Errorf("temporary file does not exist: %v", tempFilePath)
	}

	// Rename the temporary output file to the final file name
	err = os.Rename(tempFilePath, outputPdfPath)
	if err != nil {
		return fmt.Errorf("failed to rename temp file to final output file: %v", err)
	}

	// Successfully renamed the output file
	fmt.Println("Output file renamed to:", outputPdfPath)
	return nil
}

// ProcessFolder function to iterate over all PDF files in the specified folder and compress them.
func ProcessFolder(folderPath string) error {
	// Read all files in the specified folder
	files, err := os.ReadDir(folderPath)
	if err != nil {
		return fmt.Errorf("failed to read folder %s: %v", folderPath, err)
	}

	// Process each file
	for _, file := range files {
		if file.IsDir() {
			continue // Skip subdirectories
		}

		inputFile := filepath.Join(folderPath, file.Name())
		outputFile := "C:/codebase/doc_compress/Files/HTH-2024-40538/HTH-2024-40538_Compressed/HTH-2024-40538_GO_GHOSTSCRIPT/" + file.Name()

		err := processFile(inputFile, outputFile, file.Name())
		if err != nil {
			log.Printf("Error processing file %s: %v", file.Name(), err)
		}
	}
	return nil
}

// processFile handles different types of files (PDF, JPG, PNG)
func processFile(inputFile, outputFile, fileName string) error {
	ext := strings.ToLower(filepath.Ext(fileName))

	switch ext {
	case ".pdf":
		return processPDF(inputFile, outputFile)
	case ".jpg", ".png":
		return processImage(inputFile, outputFile)
	default:
		// If the file is neither PDF nor image, skip processing
		return nil
	}
}

// processPDF handles PDF compression based on file name length
func processPDF(inputFile, outputFile string) error {
	if len(outputFile) > 250 {
		return compressLengthyNamePDF(inputFile, outputFile)
	}
	return compressPDF(inputFile, outputFile)
}

// processImage handles image resizing
func processImage(inputFile, outputFile string) error {
	return resizeImage(inputFile, outputFile)
}

// func ProcessFolder(folderPath string) error {
// 	// Read all files in the specified folder
// 	files, err := os.ReadDir(folderPath)
// 	if err != nil {
// 		return fmt.Errorf("failed to read folder %s: %v", folderPath, err)
// 	}

// 	// Iterate over each file in the folder
// 	for _, file := range files {
// 		if file.IsDir() {
// 			continue // Skip subdirectories
// 		}
// 		inputFile := filepath.Join(folderPath, file.Name())
// 		outputFile := "C:/codebase/doc_compress/Files/HTH-2024-40538/HTH-2024-40538_Compressed/HTH-2024-40538_GO_GHOSTSCRIPT/" + file.Name()

// 		// Check if the file has a .pdf extension
// 		if strings.EqualFold(filepath.Ext(file.Name()), ".pdf") {
// 			// Define the full input and output file paths
// 			fileLength := len(outputFile)
// 			if fileLength > 250 {
// 				// Call the CompressPDF  to compress the current PDF
// 				err := compressLengthyNamePDF(inputFile, outputFile)
// 				if err != nil {
// 					log.Printf("Failed to compress %s: %v", file.Name(), err)
// 				} else {
// 					log.Printf("Successfully compressed: %s", file.Name())
// 				}
// 			} else {
// 				// Call the CompressPDF  to compress the current PDF
// 				err := compressPDF(inputFile, outputFile)
// 				if err != nil {
// 					log.Printf("Failed to compress %s: %v", file.Name(), err)
// 				} else {
// 					log.Printf("Successfully compressed: %s", file.Name())
// 				}
// 			}
// 		} else if strings.EqualFold(filepath.Ext(file.Name()), ".jpg") || strings.EqualFold(filepath.Ext(file.Name()), ".png") {
// 			resizeImage(inputFile, outputFile)
// 		}
// 	}
// 	return nil
// }

func StartCompression() {
	// Define the folder containing PDF files
	folderPath := "C:/codebase/doc_compress/Files/HTH-2024-40538/HTH-2024-40538/" // Change this to the directory containing your PDFs
	// Check if the folder exists
	if _, err := os.Stat(folderPath); os.IsNotExist(err) {
		log.Fatalf("Folder does not exist: %s", folderPath)
	}
	// Record start time
	startTime := time.Now()
	// Measure initial CPU and memory usage
	initialCPU := getCPUUsage()
	initialMemory := getMemoryUsage()
	// Log initial resource usage
	fmt.Printf("Initial CPU Usage: %.2f%%\n", initialCPU)
	fmt.Printf("Initial Memory Usage: %d MB\n", initialMemory/(1024*1024))
	// Start PDF compression
	fmt.Println("Starting PDF compression...")
	// Process the folder and compress the PDFs
	err := ProcessFolder(folderPath)
	if err != nil {
		log.Fatalf("Failed to process folder: %v", err)
	}
	// compressPDF(inputPdfPath, outputPdfPath);
	// Record end time and calculate the time taken
	duration := time.Since(startTime)
	// Measure final CPU and memory usage
	finalCPU := getCPUUsage()
	finalMemory := getMemoryUsage()
	// Log final resource usage
	fmt.Printf("Final CPU Usage: %.2f%%\n", finalCPU)
	fmt.Printf("Final Memory Usage: %d MB\n", finalMemory/(1024*1024))
	// Log time taken for compression
	fmt.Printf("Time taken for compression: %v\n", duration)
	// Calculate and log the differences in resource usage
	cpuDifference := finalCPU - initialCPU
	memoryDifference := finalMemory - initialMemory
	fmt.Printf("CPU Usage during compression: %.2f%%\n", cpuDifference)
	fmt.Printf("Memory Used during compression: %d MB\n", memoryDifference/(1024*1024))
	fmt.Printf("Compressed PDF saved to: %s\n")
}
