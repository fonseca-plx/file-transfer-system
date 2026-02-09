# ── File Transfer System — gRPC Build Helpers ──────────────────────────────
PROTO_SRC   := proto/file_transfer.proto
GO_OUT      := grpc-go-server/pb
PY_OUT      := grpc-python-client/pb

# ── Proto generation ───────────────────────────────────────────────────────
.PHONY: proto-go proto-py proto-all

proto-go:
	@mkdir -p $(GO_OUT)
	protoc \
		--go_out=$(GO_OUT) --go_opt=paths=source_relative \
		--go-grpc_out=$(GO_OUT) --go-grpc_opt=paths=source_relative \
		-I proto \
		$(PROTO_SRC)
	@echo "✔  Go stubs generated in $(GO_OUT)/"

proto-py:
	python3 -m grpc_tools.protoc \
		--python_out=$(PY_OUT) \
		--grpc_python_out=$(PY_OUT) \
		--pyi_out=$(PY_OUT) \
		-I proto \
		$(PROTO_SRC)
	@# Fix absolute import to relative so `from pb import ...` works
	sed -i 's/^import file_transfer_pb2/from . import file_transfer_pb2/' $(PY_OUT)/file_transfer_pb2_grpc.py
	@echo "✔  Python stubs generated in $(PY_OUT)/"

proto-all: proto-go proto-py

# ── Go server ──────────────────────────────────────────────────────────────
.PHONY: go-deps go-build run-server

go-deps:
	cd grpc-go-server && go mod tidy

go-build: go-deps
	cd grpc-go-server && go build -o server .

run-server: go-build
	cd grpc-go-server && ./server

# ── Python client ──────────────────────────────────────────────────────────
.PHONY: py-deps run-client

py-deps:
	pip install -r grpc-python-client/requirements.txt

# Usage: make run-client FILE=path/to/file
run-client:
	cd grpc-python-client && python3 client.py $(FILE)

# ── Convenience ────────────────────────────────────────────────────────────
.PHONY: setup clean

setup: proto-all go-deps py-deps
	@echo "✔  All stubs generated and dependencies installed"

clean:
	rm -rf $(GO_OUT)/*.go
	rm -rf $(PY_OUT)/file_transfer_pb2*.py $(PY_OUT)/file_transfer_pb2*.pyi
	rm -f grpc-go-server/server
	@echo "✔  Cleaned generated files"
