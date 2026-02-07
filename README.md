# File Transfer System

Plataforma de transferência de arquivos em rede utilizando Sockets (TCP + UDP) e gRPC.

---

## Sobre o Projeto

Este projeto é um estudo de caso acadêmico da disciplina de **Desenvolvimento de Sistemas Distribuídos** que implementa um sistema de **transferência de arquivos em rede com monitoramento de progresso em tempo real**.

### Objetivos

- Demonstrar o uso direto de **sockets TCP e UDP** em Python, sem frameworks ou bibliotecas de alto nível
- Separar os canais de comunicação: **TCP** para dados confiáveis e **UDP** para telemetria leve
- Definir um **protocolo de aplicação customizado** sobre TCP e UDP
- Permitir **concorrência** no servidor (múltiplos uploads simultâneos via threads)

### Funcionalidades

- Upload de arquivos de qualquer tipo e tamanho via TCP
- Monitoramento de progresso em tempo real via UDP
- Logging detalhado de toda a comunicação (`[TCP]`, `[UDP]`, `[SEND]`)
- Suporte a múltiplos clientes simultâneos
- Tolerância a falhas no canal UDP (perda de pacotes não interrompe a transferência)

---

## Arquitetura do Projeto

```
sockets-python/
├── server/                  # Lado do servidor
│   ├── __main__.py          # Ponto de entrada — inicia TCP + UDP
│   ├── tcp_server.py        # Servidor TCP — recebe e salva arquivos
│   ├── udp_server.py        # Servidor UDP — recebe e exibe progresso
│   ├── storage.py           # Escrita segura de arquivos em disco
│   └── uploads/             # Diretório onde os arquivos são salvos
│
├── client/                  # Lado do cliente
│   ├── __main__.py          # Ponto de entrada — CLI do cliente
│   ├── tcp_client.py        # Envia o arquivo por TCP em chunks
│   ├── udp_progress.py      # Envia datagramas de progresso via UDP
│   └── sender.py            # Orquestrador — conecta TCP + UDP
│
└── shared/                  # Código compartilhado
    └── protocol.py          # Protocolo de aplicação, constantes e helpers
```

**Por que essa separação?**

| Módulo   | Responsabilidade |
|----------|------------------|
| `shared/` | Contrato entre cliente e servidor — formatos de mensagem, portas, tamanho de chunks. Qualquer mudança no protocolo é feita em um único lugar. |
| `server/` | Recepção passiva — escuta conexões TCP e datagramas UDP. Cada responsabilidade (arquivo vs. progresso) fica em seu próprio módulo. |
| `client/` | Envio ativo — lê o arquivo local, transmite por TCP e reporta progresso por UDP. O `sender.py` orquestra tudo. |

---

## Como Funciona

### 1. Protocolo de Aplicação

O protocolo é definido em `shared/protocol.py` e usa dois canais independentes:

#### Canal TCP (porta 5000) — Transferência de arquivo

As mensagens de controle (`HEADER` e `END`) são enviadas com **length-prefixed framing**: antes de cada mensagem, são enviados 4 bytes (big-endian) indicando o tamanho da mensagem. Isso permite ao receptor saber exatamente quantos bytes ler.

| Etapa | Formato | Exemplo |
|-------|---------|---------|
| Início | `HEADER\|<nome_arquivo>\|<tamanho_bytes>\n` | `HEADER\|foto.jpg\|50000\n` |
| Dados | Bytes brutos em pedaços de 4096 bytes | `[4096 bytes]` `[4096 bytes]` ... |
| Fim | `END\n` | `END\n` |

#### Canal UDP (porta 5001) — Telemetria de progresso

Cada datagrama é independente e autocontido:

| Formato | Exemplo |
|---------|---------|
| `PROGRESS\|<nome_arquivo>\|<percentual>\n` | `PROGRESS\|foto.jpg\|41.0\n` |

---

### 2. Fluxo Completo de uma Transferência

```
        CLIENTE                                    SERVIDOR
           │                                          │
     ┌─────┴─────┐                             ┌──────┴──────┐
     │ sender.py │                             │ __main__.py │
     └─────┬─────┘                             └──────┬──────┘
           │                                          │
           │  ① TCP connect ──────────────────────►  :5000  (tcp_server.py)
           │                                          │
           │  ② HEADER|foto.jpg|50000 ────────────►   │  → decode_header()
           │                                          │  → abre FileWriter
           │                                          │
           │  ③ [4096 bytes] ─────────────────────►   │  → writer.write_chunk()
           │     [4096 bytes] ─────────────────────►  │  → writer.write_chunk()
           │     [4096 bytes] ─────────────────────►  │  → writer.write_chunk()
           │     [4096 bytes] ─────────────────────►  │  → writer.write_chunk()
           │     [4096 bytes] ─────────────────────►  │  → writer.write_chunk()
           │                                          │
           │  ④ UDP PROGRESS|foto.jpg|41.0 ·······►  :5001  (udp_server.py)
           │     (a cada 5 chunks)                    │  → log de progresso
           │                                          │
           │     ... continua chunks TCP ...          │
           │     [últimos bytes] ─────────────────►   │
           │                                          │
           │  ⑤ UDP PROGRESS|foto.jpg|100.0 ······►  :5001
           │     (sempre envia ao final)              │
           │                                          │
           │  ⑥ END ─────────────────────────────►    │  → fecha FileWriter
           │                                          │  → arquivo salvo em uploads/
           │  ⑦ TCP close ───────────────────────►    │
           │                                          │
```

#### Passo a passo detalhado:

1. **Inicialização do servidor** (`python3 -m server`): o `__main__.py` cria uma **thread daemon** para o servidor UDP e roda o servidor TCP na **thread principal**. Ambos começam a escutar simultaneamente.

2. **Conexão TCP** (`①`): o cliente (`tcp_client.py`) cria um socket TCP e conecta em `localhost:5000`. O servidor aceita a conexão e cria uma **nova thread** dedicada para aquele cliente.

3. **Envio do HEADER** (`②`): o cliente envia uma mensagem length-prefixed contendo `HEADER|nome_arquivo|tamanho`. O servidor decodifica e abre um `FileWriter` para o arquivo de destino em `server/uploads/`.

4. **Envio dos chunks** (`③`): o cliente lê o arquivo local em pedaços de **4096 bytes** e os envia como bytes brutos pelo socket TCP. O servidor recebe e escreve cada pedaço diretamente em disco. O `tcp_client.py` usa um **generator** (`yield`) que retorna `(bytes_enviados, total)` a cada chunk.

5. **Progresso via UDP** (`④` e `⑤`): o `sender.py` consome o generator do TCP e, **a cada 5 chunks**, dispara um datagrama `PROGRESS|arquivo|percentual` via UDP na porta `5001`. O servidor UDP apenas loga a informação. Se o datagrama se perder, nada acontece — o upload continua normalmente.

6. **Finalização** (`⑥` e `⑦`): após o último byte do arquivo, o cliente envia a mensagem `END` (length-prefixed). O servidor verifica o marcador, fecha o `FileWriter` e encerra a conexão TCP.

---

### 3. Responsabilidades: TCP vs UDP

| Aspecto | Servidor TCP (`:5000`) | Servidor UDP (`:5001`) |
|---------|------------------------|------------------------|
| **Protocolo** | TCP — confiável, ordenado, com conexão | UDP — sem conexão, sem garantia de entrega |
| **Função** | Receber e salvar o arquivo em disco | Receber e exibir o progresso no log |
| **Dados** | Bytes brutos do arquivo (críticos) | Texto leve: `PROGRESS\|arquivo\|%` (descartável) |
| **Se falhar** | O upload falha — o arquivo fica corrompido | Nada acontece — o upload continua normalmente |
| **Concorrência** | Uma thread por cliente conectado | Uma única thread daemon |
| **Por que esse protocolo?** | Arquivos exigem entrega **confiável e ordenada** | Progresso é informação auxiliar — perda é aceitável |

---

## Como Executar e Testar

### Pré-requisitos

- **Python 3.10+** (utiliza type union `X | None`)
- Nenhuma dependência externa — apenas a biblioteca padrão do Python

### Passo 1 — Iniciar o servidor

Abra um terminal e execute:

```bash
cd sockets-python/
python3 -m server
```

Saída esperada:

```
2026-02-07 17:20:20,381 INFO     [MAIN] UDP thread started
2026-02-07 17:20:20,382 INFO     [MAIN] Starting TCP server on main thread
2026-02-07 17:20:20,382 INFO     [TCP] Server listening on localhost:5000
2026-02-07 17:20:20,382 INFO     [UDP] Listening on localhost:5001
```

### Passo 2 — Enviar um arquivo

Em **outro terminal**, execute:

```bash
cd sockets-python/
python3 -m client caminho/do/arquivo.ext
```

Exemplo com um arquivo de teste:

```bash
# Criar um arquivo de teste de 50 KB
head -c 50000 /dev/urandom > /tmp/testfile.bin

# Enviar
python3 -m client /tmp/testfile.bin
```

Saída esperada (cliente):

```
2026-02-07 17:23:03,112 INFO     [TCP] Connected to localhost:5000
2026-02-07 17:23:03,113 INFO     [TCP] Sent HEADER — file=testfile.bin size=50000
2026-02-07 17:23:03,116 INFO     [SEND] testfile.bin — 41.0% (20480/50000 bytes)
2026-02-07 17:23:03,117 INFO     [SEND] testfile.bin — 81.9% (40960/50000 bytes)
2026-02-07 17:23:03,117 INFO     [SEND] testfile.bin — 100.0% (50000/50000 bytes)
2026-02-07 17:23:03,117 INFO     [TCP] Sent END — upload finished
2026-02-07 17:23:03,118 INFO     [SEND] Transfer complete: testfile.bin
```

O arquivo ficará salvo em `sockets-python/server/uploads/`.

### Passo 3 — Verificar integridade

```bash
md5sum /tmp/testfile.bin
md5sum sockets-python/server/uploads/testfile.bin
```

Os hashes devem ser idênticos.

### Testes de falha sugeridos

| Cenário | Como testar | Comportamento esperado |
|---------|-------------|------------------------|
| **Servidor UDP desligado** | Não iniciar o servidor, ou matar a thread | Upload TCP completa normalmente; logs de progresso mostram warnings |
| **Arquivo grande** | `head -c 100000000 /dev/urandom > /tmp/big.bin` (100 MB) | Upload funciona, progresso atualizado a cada 5 chunks |
| **Cliente interrompido** | `Ctrl+C` durante o upload | Servidor detecta desconexão e loga erro; arquivo parcial pode existir |
| **Múltiplos clientes** | Rodar dois clientes em terminais separados ao mesmo tempo | Servidor atende ambos em threads independentes |
