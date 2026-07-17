# Step 1: Use the official Golang image as the builder
FROM golang:1.22 as builder


ARG AZDOCOCR_FOIDOCREVIEWER_DB_HOST
ARG AZDOCOCR_FOIDOCREVIEWER_DB_PORT
ARG AZDOCOCR_FOIDOCREVIEWER_DB_NAME
ARG AZDOCOCR_FOIDOCREVIEWER_DB_USERNAME
ARG AZDOCOCR_FOIDOCREVIEWER_DB_PASSWORD
ARG AZDOCOCR_LISTENING_PORT
ARG AZDOCOCR_API_SECRET
ARG AZDOCOCR_ALLOWED_ORIGINS

ENV AZDOCOCR_FOIDOCREVIEWER_DB_HOST=${AZDOCOCR_FOIDOCREVIEWER_DB_HOST}
ENV AZDOCOCR_FOIDOCREVIEWER_DB_PORT=${AZDOCOCR_FOIDOCREVIEWER_DB_PORT}
ENV AZDOCOCR_FOIDOCREVIEWER_DB_NAME=${AZDOCOCR_FOIDOCREVIEWER_DB_NAME}
ENV AZDOCOCR_FOIDOCREVIEWER_DB_USERNAME=${AZDOCOCR_FOIDOCREVIEWER_DB_USERNAME}
ENV AZDOCOCR_FOIDOCREVIEWER_DB_PASSWORD=${AZDOCOCR_FOIDOCREVIEWER_DB_PASSWORD}
ENV AZDOCOCR_LISTENING_PORT=${AZDOCOCR_LISTENING_PORT}
ENV AZDOCOCR_API_SECRET=${AZDOCOCR_API_SECRET}
ENV AZDOCOCR_ALLOWED_ORIGINS=${AZDOCOCR_ALLOWED_ORIGINS}


# Create a directory for the application
RUN mkdir -p /app

# Set the working directory inside the container
WORKDIR /app

# Copy go mod and sum files for dependency management
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy the source code into the container
COPY . .

# Build the Go application
RUN go build -o azuredococrapi .

# Step 2: Use a minimal image for the final container
#FROM alpine:latest

# # Set up working directory
# WORKDIR /root/

# # Copy the compiled binary from the builder stage
# COPY --from=builder /app/azuredococrapi .

# Expose the port your API will run on (default 8080 in most examples)
EXPOSE 52863

# Command to run the API
CMD ["./azuredococrapi"]
