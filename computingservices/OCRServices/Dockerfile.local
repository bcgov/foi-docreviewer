# ---------- Build Stage ----------
    FROM golang:1.24.3-alpine AS builder

    # Create a directory for the application
    RUN mkdir -p /app

    WORKDIR /app
    
    COPY go.mod go.sum ./
    RUN go mod download
    
    COPY . .
    RUN go build -o ocr-service .
    
    # ---------- Final Image ----------
    FROM alpine:3.21
        
    WORKDIR /app
    
    # #Copy the binary from builder stage
    COPY --from=builder /app/ocr-service .
    
    RUN chmod +x ./ocr-service
    
    CMD ["./ocr-service"]
