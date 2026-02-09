# File Transfer System

Plataforma de transferência de arquivos em rede utilizando **gRPC** com streaming — servidor em **Go** e cliente em **Python**.

---

## Sobre o Projeto

Este projeto é um estudo de caso acadêmico da disciplina de **Desenvolvimento de Sistemas Distribuídos** que implementa um sistema de **transferência de arquivos em rede** utilizando **gRPC com client-side streaming**.

### Objetivos

- Demonstrar comunicação baseada em **RPC** com contratos tipados (Protocol Buffers)
- Utilizar **streaming gRPC** para transmissão eficiente de arquivos em chunks
- Implementar **interoperabilidade entre linguagens** — servidor Go + cliente Python
- Permitir comparação direta com a versão baseada em sockets

### Funcionalidades

- Upload de arquivos de qualquer tipo e tamanho via gRPC streaming
- Monitoramento de progresso em tempo real (logs no cliente e no servidor)
- Logging detalhado de toda a comunicação (`[gRPC]`, `[SEND]`)
- Contrato de serviço definido em Protocol Buffers (`.proto`)
- Geração automática de stubs para Go e Python

---

## Arquitetura do Projeto

```
.
├── proto/                       # Definição do contrato gRPC
│   └── file_transfer.proto      # Serviço, mensagens e tipos
│
├── grpc-go-server/              # Servidor (Go)
│   ├── main.go                  # Ponto de entrada — implementa o serviço
│   ├── go.mod / go.sum          # Dependências Go
│   ├── pb/                      # Stubs gerados (protoc)
│   │   ├── file_transfer.pb.go
│   │   └── file_transfer_grpc.pb.go
│   └── uploads/                 # Diretório onde os arquivos são salvos
│
├── grpc-python-client/          # Cliente (Python)
│   ├── client.py                # Ponto de entrada — CLI + upload streaming
│   ├── requirements.txt         # Dependências Python (grpcio, grpcio-tools)
│   └── pb/                      # Stubs gerados (grpc_tools.protoc)
│       ├── file_transfer_pb2.py
│       ├── file_transfer_pb2_grpc.py
│       └── file_transfer_pb2.pyi
│
└── Makefile                     # Geração de stubs, build e execução
```

**Responsabilidade de cada módulo:**

| Módulo | Responsabilidade |
|--------|------------------|
| `proto/` | **Contrato compartilhado** — define as mensagens (`Chunk`, `FileMetadata`, `UploadStatus`) e o serviço (`FileTransfer`). Qualquer mudança na API é feita aqui e propagada via geração de stubs. |
| `grpc-go-server/` | **Recepção** — escuta na porta `50051`, recebe o stream de chunks, extrai metadata, escreve o arquivo em `uploads/` e retorna o status. |
| `grpc-python-client/` | **Envio** — lê o arquivo local em chunks de 4096 bytes, gera um iterador de mensagens `Chunk` e transmite via streaming gRPC. |

---

## Como Funciona

### 1. Contrato de Serviço (Protocol Buffers)

O contrato é definido em `proto/file_transfer.proto`:

```protobuf
service FileTransfer {
  rpc Upload(stream Chunk) returns (UploadStatus);
}

message Chunk {
  oneof payload {
    FileMetadata metadata = 1;  // Primeiro chunk: nome e tamanho
    bytes        data     = 2;  // Chunks seguintes: bytes do arquivo
  }
}

message FileMetadata {
  string filename  = 1;
  int64  file_size = 2;
}

message UploadStatus {
  string filename       = 1;
  int64  bytes_received = 2;
  string message        = 3;
}
```

**Por que `oneof`?** Permite reutilizar a mesma mensagem `Chunk` tanto para metadata quanto para dados, evitando um RPC separado. O primeiro chunk do stream **sempre** carrega `FileMetadata`; todos os demais carregam `data`.

---

### 2. Fluxo Completo de uma Transferência

```
     CLIENTE (Python)                              SERVIDOR (Go)
           │                                          │
     ┌─────┴─────┐                             ┌──────┴──────┐
     │ client.py │                             │   main.go   │
     └─────┬─────┘                             └──────┬──────┘
           │                                          │
           │  ① gRPC connect ─────────────────────►  :50051
           │                                          │
           │  ② Chunk{metadata: {                     │
           │       filename: "foto.jpg",              │
           │       file_size: 51200                   │
           │     }} ──────────────────────────────►   │  → abre arquivo em uploads/
           │                                          │
           │  ③ Chunk{data: [4096 bytes]} ────────►   │  → dst.Write(data)
           │     Chunk{data: [4096 bytes]} ────────►  │  → dst.Write(data)
           │     Chunk{data: [4096 bytes]} ────────►  │  → dst.Write(data)
           │     Chunk{data: [4096 bytes]} ────────►  │  → dst.Write(data)
           │     Chunk{data: [4096 bytes]} ────────►  │  → dst.Write(data)
           │                                          │
           │     (cliente loga progresso a cada       │  (servidor loga progresso
           │      5 chunks: [SEND] 40.0%)             │   a cada 5 chunks: [gRPC] 40.0%)
           │                                          │
           │     ... continua chunks ...              │
           │     Chunk{data: [últimos bytes]} ─────►  │
           │                                          │
           │  ④ EOF (stream encerrado) ───────────►   │  → fecha arquivo
           │                                          │
           │  ⑤ UploadStatus {                        │
           │       filename: "foto.jpg",              │
           │       bytes_received: 51200,             │
           │       message: "Upload succeeded"        │
           │     } ◄──────────────────────────────    │
           │                                          │
           │  ⑥ Canal fechado                         │
           │                                          │
```

#### Passo a passo detalhado:

1. **Conexão gRPC** (`①`): o cliente cria um canal inseguro (`grpc.insecure_channel`) para `localhost:50051` e obtém um stub do serviço `FileTransfer`.

2. **Envio de metadata** (`②`): o primeiro `Chunk` do stream carrega `FileMetadata` com o nome e tamanho do arquivo. O servidor extrai esses dados e cria o arquivo de destino em `uploads/`.

3. **Streaming de dados** (`③`): o cliente usa um **generator Python** (`_chunk_iterator`) que lê o arquivo em pedaços de **4096 bytes** e faz `yield` de mensagens `Chunk(data=...)`. O gRPC cuida da serialização, framing e transporte. A cada 5 chunks, ambos os lados logam o progresso.

4. **Fim do stream** (`④`): quando o generator se esgota, o gRPC sinaliza EOF. O servidor fecha o arquivo em disco.

5. **Resposta** (`⑤`): o servidor chama `SendAndClose` com `UploadStatus` contendo o total de bytes recebidos e uma mensagem de confirmação.

6. **Encerramento** (`⑥`): o cliente lê a resposta, loga o resultado e fecha o canal.

---

### 3. Comparação: gRPC vs Sockets

| Aspecto | Sockets (TCP + UDP) | gRPC |
|---------|---------------------|------|
| **Protocolo** | Customizado (`HEADER\|END`), framing manual | Protocol Buffers — tipado, versionável |
| **Transporte** | TCP (arquivo) + UDP (progresso) — 2 portas | HTTP/2 multiplexado — 1 porta |
| **Progresso** | Canal separado UDP, tolerante a perda | Logs locais em ambos os lados (mesmo stream) |
| **Serialização** | Manual (`encode`/`decode`, `struct.pack`) | Automática (protobuf) |
| **Linguagens** | Python-only | Go (servidor) + Python (cliente) — interoperável |
| **Complexidade** | Alta — gerenciar sockets, threads, protocolo | Baixa — definir `.proto`, gerar stubs, implementar |
| **Linhas de código** | ~250 (7 arquivos Python + shared) | ~150 (1 Go + 1 Python + 1 proto) |
| **Confiabilidade** | TCP confiável, UDP não — lógica manual | gRPC sobre HTTP/2 — confiável por padrão |
| **Streaming** | Generator manual sobre socket raw | `stream` nativo no contrato `.proto` |

---

## Pré-requisitos

- **Go 1.18+**
- **Python 3.10+**
- **protoc** (Protocol Buffers compiler)
- **protoc-gen-go** e **protoc-gen-go-grpc** (plugins Go para protoc)
- **grpcio** e **grpcio-tools** (pacotes Python)

### Instalação das dependências

```bash
# protoc e Go (Ubuntu/Debian)
sudo apt install golang-go protobuf-compiler

# Plugins Go para protoc
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

# Adicionar ao PATH (se necessário)
export PATH="$PATH:$(go env GOPATH)/bin"

# Setup completo (gera stubs + instala deps Python)
make setup
```

---

## Como Executar e Testar

### Passo 1 — Gerar stubs e instalar dependências

```bash
make setup
```

Isso executa:
- `make proto-go` — gera stubs Go em `grpc-go-server/pb/`
- `make proto-py` — gera stubs Python em `grpc-python-client/pb/`
- `make go-deps` — baixa dependências Go
- `make py-deps` — instala pacotes Python

### Passo 2 — Iniciar o servidor Go

Abra um terminal e execute:

```bash
make run-server
```

Saída esperada:

```
2026/02/07 20:52:06 [gRPC] Server listening on :50051
```

### Passo 3 — Enviar um arquivo

Em **outro terminal**, execute:

```bash
make run-client FILE=/caminho/do/arquivo.ext
```

Exemplo com um arquivo de teste:

```bash
# Criar um arquivo de teste de 50 KB
head -c 51200 /dev/urandom > /tmp/testfile.bin

# Enviar
make run-client FILE=/tmp/testfile.bin
```

Saída esperada (cliente):

```
2026-02-07 20:52:26,360 INFO     [gRPC] Connecting to localhost:50051
2026-02-07 20:52:26,401 INFO     [gRPC] Sending metadata — file=testfile.bin size=51200
2026-02-07 20:52:26,403 INFO     [SEND] testfile.bin — 40.0% (20480/51200 bytes)
2026-02-07 20:52:26,404 INFO     [SEND] testfile.bin — 80.0% (40960/51200 bytes)
2026-02-07 20:52:26,405 INFO     [SEND] Finished streaming: testfile.bin — 51200 bytes in 13 chunks
2026-02-07 20:52:26,406 INFO     [gRPC] Server response — file=testfile.bin bytes_received=51200 message='Upload of 'testfile.bin' succeeded'
2026-02-07 20:52:26,407 INFO     [SEND] Transfer complete: testfile.bin
```

Saída esperada (servidor):

```
2026/02/07 20:52:26 [gRPC] Receiving file: testfile.bin (51200 bytes)
2026/02/07 20:52:26 [gRPC] testfile.bin — 40.0% (20480/51200 bytes)
2026/02/07 20:52:26 [gRPC] testfile.bin — 80.0% (40960/51200 bytes)
2026/02/07 20:52:26 [gRPC] Upload complete: testfile.bin — 51200 bytes received in 13 chunks
```

O arquivo ficará salvo em `grpc-go-server/uploads/`.

### Passo 4 — Verificar integridade

```bash
md5sum /tmp/testfile.bin
md5sum grpc-go-server/uploads/testfile.bin
```

Os hashes devem ser idênticos.

### Testes sugeridos

| Cenário | Como testar | Comportamento esperado |
|---------|-------------|------------------------|
| **Servidor desligado** | Rodar o cliente sem o servidor | `RPC failed: StatusCode.UNAVAILABLE` — erro claro e imediato |
| **Arquivo grande** | `head -c 100000000 /dev/urandom > /tmp/big.bin` (100 MB) | Upload funciona, progresso atualizado a cada 5 chunks |
| **Cliente interrompido** | `Ctrl+C` durante o upload | Servidor detecta stream encerrado e loga erro |
| **Arquivo inexistente** | `make run-client FILE=/nao/existe` | `[gRPC] File not found` — validação local antes do RPC |

---

## Comandos do Makefile

| Comando | Descrição |
|---------|-----------|
| `make setup` | Gera todos os stubs + instala dependências |
| `make proto-all` | Gera stubs Go e Python |
| `make proto-go` | Gera apenas stubs Go |
| `make proto-py` | Gera apenas stubs Python |
| `make run-server` | Compila e inicia o servidor Go |
| `make run-client FILE=...` | Envia um arquivo via o cliente Python |
| `make go-build` | Apenas compila o servidor Go |
| `make clean` | Remove stubs gerados e binários |
