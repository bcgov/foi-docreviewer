package compressor

import (
	"bytes"
	"context"
	"io"
)

const scanChunkSize = 64 * 1024

var jbig2Marker = []byte("/JBIG2Decode")

func scanJBIG2(ctx context.Context, reader io.Reader) (bool, error) {
	overlap := len(jbig2Marker) - 1
	buffer := make([]byte, scanChunkSize+overlap)
	carried := 0

	for {
		if err := ctx.Err(); err != nil {
			return false, err
		}

		n, readErr := reader.Read(buffer[carried : carried+scanChunkSize])
		if err := ctx.Err(); err != nil {
			return false, err
		}
		window := buffer[:carried+n]
		if bytes.Contains(window, jbig2Marker) {
			return true, nil
		}

		if len(window) < overlap {
			carried = copy(buffer, window)
		} else {
			carried = copy(buffer, window[len(window)-overlap:])
		}

		switch readErr {
		case nil:
			continue
		case io.EOF:
			return false, nil
		default:
			return false, readErr
		}
	}
}
