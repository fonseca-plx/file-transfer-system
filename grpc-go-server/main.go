package main

import (
	"fmt"
	"io"
	"log"
	"net"
	"os"
	"path/filepath"

	pb "github.com/pedrofonseca/file-transfer-system/grpc-go-server/pb"

	"google.golang.org/grpc"
)

const (
	port      = ":50051"
	uploadDir = "uploads"
)

// server implements the FileTransfer gRPC service.
type server struct {
	pb.UnimplementedFileTransferServer
}

// Upload handles a client-streaming RPC.
// First chunk MUST carry metadata; subsequent chunks carry raw bytes.
func (s *server) Upload(stream pb.FileTransfer_UploadServer) error {
	// ── 1. Receive first chunk (metadata) ──────────────────────────────
	firstChunk, err := stream.Recv()
	if err != nil {
		log.Printf("[gRPC] Error receiving first chunk: %v", err)
		return fmt.Errorf("failed to receive metadata: %w", err)
	}

	meta := firstChunk.GetMetadata()
	if meta == nil {
		log.Println("[gRPC] First chunk does not contain metadata")
		return fmt.Errorf("first chunk must contain file metadata")
	}

	filename := filepath.Base(meta.GetFilename()) // sanitise
	fileSize := meta.GetFileSize()
	log.Printf("[gRPC] Receiving file: %s (%d bytes)", filename, fileSize)

	// ── 2. Create destination file ─────────────────────────────────────
	if err := os.MkdirAll(uploadDir, 0o755); err != nil {
		return fmt.Errorf("failed to create upload dir: %w", err)
	}
	dst, err := os.Create(filepath.Join(uploadDir, filename))
	if err != nil {
		return fmt.Errorf("failed to create file: %w", err)
	}
	defer dst.Close()

	// ── 3. Receive data chunks ─────────────────────────────────────────
	var bytesReceived int64
	chunkCount := 0

	for {
		chunk, err := stream.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			log.Printf("[gRPC] Error receiving chunk: %v", err)
			return fmt.Errorf("error receiving chunk: %w", err)
		}

		data := chunk.GetData()
		if data == nil {
			continue // ignore unexpected metadata messages
		}

		n, err := dst.Write(data)
		if err != nil {
			return fmt.Errorf("error writing to file: %w", err)
		}
		bytesReceived += int64(n)
		chunkCount++

		if chunkCount%5 == 0 && fileSize > 0 {
			pct := float64(bytesReceived) / float64(fileSize) * 100
			log.Printf("[gRPC] %s — %.1f%% (%d/%d bytes)", filename, pct, bytesReceived, fileSize)
		}
	}

	log.Printf("[gRPC] Upload complete: %s — %d bytes received in %d chunks", filename, bytesReceived, chunkCount)

	// ── 4. Reply with status ───────────────────────────────────────────
	return stream.SendAndClose(&pb.UploadStatus{
		Filename:      filename,
		BytesReceived: bytesReceived,
		Message:       fmt.Sprintf("Upload of '%s' succeeded", filename),
	})
}

func main() {
	log.SetFlags(log.LstdFlags)

	lis, err := net.Listen("tcp", port)
	if err != nil {
		log.Fatalf("[gRPC] Failed to listen on %s: %v", port, err)
	}

	grpcServer := grpc.NewServer()
	pb.RegisterFileTransferServer(grpcServer, &server{})

	log.Printf("[gRPC] Server listening on %s", port)
	if err := grpcServer.Serve(lis); err != nil {
		log.Fatalf("[gRPC] Failed to serve: %v", err)
	}
}
