# ---------- Build Stage ----------
    FROM golang:1.24.0-alpine AS builder
    
    # Create a directory for the application
    RUN mkdir -p /app
    
    WORKDIR /app
    
    COPY go.mod go.sum ./
    RUN go mod download
    
    COPY . .
    RUN go build -o compression-service .
    
    # ---------- Final Image ----------
    FROM alpine:3.21
    
    RUN apk --no-cache add ca-certificates ghostscript
    
    WORKDIR /app
    
    # Copy the binary from builder stage
    COPY --from=builder /app/compression-service .

    # Make sure it’s executable
    RUN chmod +x ./compression-service

    # Copy .env to the container
    #COPY .env .env

    # COPY .env /app/.env

    #RUN chmod +x ./compression-service
    #RUN chmod 644 .env
    
    # ENTRYPOINT ["/entrypoint.sh"]
    
    CMD ["./compression-service"]
