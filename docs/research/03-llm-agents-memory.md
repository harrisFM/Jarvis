# Research Note 03 — The brain: LLMs, inference servers, agent frameworks, MCP, memory, safety, cost

Research date: 2026-09-11. Anthropic figures are from platform.claude.com / code.claude.com primary docs (verified directly in-session). OpenAI, Google, xAI, and several benchmark blogs were cited from search snippets because their domains were unreachable from the research environment; those rows carry **[uncertain]**.

## 1. Frontier cloud LLMs (Sept 2026)

### 1.1 Anthropic (primary source)

| Model | Released | Price in/out per MTok | Cache read | Context / max out | Latency tier | Notes |
|---|---|---|---|---|---|---|
| Claude Fable 5.1 (`claude-fable-5-1`) | 1 Sep 2026 | $10 / $50 | $0.25 (2.5%) | 1M / 128K | "Slower" | Adaptive thinking always on; forced tool use not supported |
| Claude Opus 5 (`claude-opus-5`) | 24 Jul 2026 | $5 / $25 | $0.50 | 1M / 128K | "Moderate" | Fast mode (preview): up to 2.5x output tok/s at $10/$50; effort ladder low→max; Anthropic's "start here" model |
| Claude Sonnet 5 (`claude-sonnet-5`) | 30 Jun 2026 | $2 / $10 | $0.20 | 1M / 128K | "Fast" | Introductory price made permanent; new tokenizer ≈30% more tokens than Sonnet 4.6; supports computer/browser toolsets |
| Claude Haiku 4.5 (`claude-haiku-4-5`) | 15 Oct 2025 | $1 / $5 | $0.10 | 200K / 64K | "Fastest" | Only Haiku tier; retirement not before 15 Oct 2026 |

Other Anthropic facts: Batch API 50% off; 5-min cache write 1.25x, 1-hour 2x; full 1M context at standard per-token price; web search $10 per 1,000 searches; tool-use system prompt overhead 286 tokens (Opus 5), 354 (Sonnet 5), 496 (Haiku 4.5); computer-use toolset adds ≈4,500 input tokens per request, browser toolset ≈6,600. Server-side compaction (beta, default trigger 150K tokens) and the client-side memory tool (`memory_20250818`) are the built-in long-conversation primitives. Anthropic has **no public speech-to-speech or audio-input API** on the Messages API (text + image in, text out). Claude Code's `/voice` mode uses server-side transcription and ElevenLabs TTS (TechCrunch, 3 Mar 2026).

Latency (Artificial Analysis snippet): Sonnet 5 non-reasoning TTFT **0.97 s**; thinking at max effort dominates TTFT (178 s). Fast mode improves output tok/s, not TTFT.

### 1.2 OpenAI [uncertain — secondary sources]

| Model | Released | Price in/out per MTok | Context | Notes |
|---|---|---|---|---|
| GPT-5.6 Sol | GA 9 Jul 2026 | $5 / $30 (cached $0.50) | 1.05M | Flagship |
| GPT-5.6 Terra | GA 9 Jul 2026 | $2 / $12 | 1.05M | TTFT 1.33 s non-reasoning |
| GPT-5.6 Luna | GA 9 Jul 2026 | $0.20 / $1.20 | 1.05M | Cheapest |
| GPT-5.5 | 24 Apr 2026 | $5 / $30 | 1M | |
| GPT-6 "Astra" | Sep 2026 | $5 / $25 | unknown | **[uncertain — one aggregator]** |

OpenAI Agents SDK (29.4k stars): guardrails, human-in-the-loop, sessions, handoffs, tracing, MCP, `RealtimeAgent` voice. ChatGPT memory "dreaming" rebuilt 4 Jun 2026 (consumer; no developer memory API found).

### 1.3 Google [uncertain — secondary]
Gemini 3.1 Pro ($2/$12) remains the Pro flagship; **Gemini 3.5 Pro delayed indefinitely as of Aug 2026**. Gemini 3.5 Flash (19 May 2026, $1.50/$9); Gemini 3.6 Flash (21 Jul 2026, $0.75/$3.75; TTFT 15.5 s at "high" thinking).

### 1.4 xAI [uncertain — secondary]
Grok 4.5 (Jul 2026) / 4.6 (Aug 2026): $2/$6, 500K context; price doubles above 200K input. Grok 5 not released.

### 1.5 Mistral
Mistral Small 4: Apache 2.0, 119B MoE, 256K; API $0.15/MTok input. Mistral Medium 3.5: dense 128B, $1.50/$7.50. Devstral 2.

### 1.6 Who is best for what (cloud)
- **Tool calling / long-horizon agents:** Claude Opus 5 and GPT-5.6 Sol; Fable 5.1 only when Opus 5 at high effort falls short.
- **Low-latency conversational turns:** Sonnet 5 (0.97 s TTFT with thinking off), GPT-5.6 Terra (1.33 s), Haiku 4.5. Gemini Flash with thinking on is *not* low latency.
- **Long context:** every vendor ~1M; Anthropic no long-context premium; xAI doubles above 200K.
- **Cheapest capable tier:** GPT-5.6 Luna, Gemini 3.6 Flash.

## 2. Open-weight local LLMs

| Model | Released | Params (total/active) | License | Context | Key numbers |
|---|---|---|---|---|---|
| Qwen3.6-35B-A3B | Apr 2026 | 35B / 3B | Apache 2.0 | 262K (1M YaRN) | SWE-bench Verified 73.4, GPQA 86.0 |
| Qwen3.6-27B (dense) | Apr 2026 | 27B | Apache 2.0 | 262K | SWE-bench Verified 77.2 |
| Qwen3.8-27B | Aug 2026 | 27B | n/a | — | Native MTP heads |
| Gemma 4 (E2B / E4B / 12B / 26B-A4B / 31B) | 2 Apr 2026 | — | **Apache 2.0** | 128K–256K | "12B genuinely good assistant at 16GB"; 26B-A4B for local coding |
| gpt-oss-120b / 20b | 5 Aug 2025 | 117B/5.1B; 21B/3.6B | Apache 2.0 | — | MXFP4; 120b ≈ 60 GB; 20b in 16 GB; no gpt-oss-2 as of mid-2026 |
| DeepSeek V4 Pro / Flash | preview 24 Apr 2026 | 1.6T/49B; 284B/13B | MIT | 1M | API off-peak $0.66/$1.98 (Pro), $0.22/$0.66 (Flash) |
| DeepSeek V4.1 Flash | mid-2026 | 552B / 8–16B | MIT | — | KV cache 1/4 of V4 Flash |
| GLM-5.1 / 5.3 / 5.3-Flash | Apr / Aug 2026 | 754B/40B; 743B/40B; 320B/18B | MIT / bespoke / MIT | 1M | GLM-5.1 SWE-bench Pro 58.4 |
| Kimi K3 | 26 Jul 2026 | 2.8T / 104B | Kimi K3 License | 1M | Native vision; multi-node only |
| Llama 4 Scout / Maverick | 5 Apr 2025 | 109B; ~400B | Llama license | 10M / 1M | **No 2026 Llama release; Behemoth shelved; Meta shipped closed Muse Spark Apr 2026** |
| Mistral Small 4 | 2026 | 119B MoE | Apache 2.0 | 256K | |

### 2.1 What fits where (quantized)

| Memory | Realistic picks |
|---|---|
| 16–24 GB | Gemma 4 12B, gpt-oss-20b, Qwen3.6-27B Q4 (RTX 3090 with MTP ~60 tok/s) |
| 32 GB (RTX 5090) | Qwen3.6-35B-A3B ("best all-round model most people can run"); Gemma 4 26B-A4B/31B Q4 |
| 96–128 GB (DGX Spark, Strix Halo, Mac M5 Max) | gpt-oss-120b (≈60 GB), Mistral Small 4 Q4, Gemma 4 31B Q8; GLM-5.3-Flash Q4 borderline [uncertain] |
| 256–512 GB (Mac M5 Ultra, multi-GPU) | DeepSeek V4 Flash 284B Q4–Q8, GLM-5.3-Flash, Qwen3.5-397B |

### 2.2 Throughput (single-stream, published)

| Hardware | Measured tokens/s | Price |
|---|---|---|
| RTX 5090 (32 GB) | 205 tok/s gpt-oss-20b; ≈7,200 tok/s prompt processing (8B) | see note 04 |
| DGX Spark (128 GB) | 38.6–60.6 tok/s gpt-oss-120b depending on runtime/benchmark; prefill ≈1,200–1,956 tok/s | $3,699–4,699 |
| Strix Halo (128 GB) | 31–34 tok/s gpt-oss-120b | $2,000–3,450 |
| Mac Studio M5 Max (128 GB, 614 GB/s) | 95–110 tok/s on 7B Q4; prefill ≈400 tok/s (8B) | from $2,499 |
| Qwen3.6 with MTP (Unsloth), RTX 6000 | 27B: 160 tok/s; 35B-A3B: 240 tok/s | — |

Rule from the reviews: an RTX 5090 is 2.7–4x faster than unified-memory boxes at anything that fits in 32 GB and useless for anything that doesn't; Spark and Strix Halo trade speed for 128 GB capacity; Macs win on bandwidth per dollar at the 128–512 GB tier but lose on prefill.

## 3. Local inference servers

| Server | Strengths | Tool calling | Speculative decoding | Prefix/KV caching |
|---|---|---|---|---|
| **llama.cpp / llama-server** | GGUF, runs anywhere; OpenAI-compatible **and Anthropic Messages-compatible** endpoints; built-in MCP integration; JSON-schema grammars; `--parallel N` | `--jinja` required; native parsers for Llama 3.x, Qwen, Mistral, Hermes, DeepSeek; **extreme KV quant (q4_0) degrades tool calling** | `--spec-type` draft / eagle3 / **mtp** / ngram; MTP 1.4–2x dense, 1.15–1.25x MoE | `--cache-prompt`, `--cache-reuse` |
| **vLLM** | Highest multi-user throughput | Yes | EAGLE 3.1 | Automatic prefix caching |
| **SGLang** | Lower latency than vLLM for structured JSON / tool loops | Yes | Yes | RadixAttention |
| **Ollama** | Packaged; v0.33.2 (Sep 2026); agent mode | Yes | flag-enabled | Yes |
| **LM Studio** | v0.4.23: llama.cpp + MLX engines, OpenAI- and Anthropic-compatible API; KV-cache checkpointing | Yes | via engines | checkpointing |
| **TensorRT-LLM** | Fastest on NVIDIA datacenter | Yes | Yes | Yes |
| **MLX** | Apple Silicon native | via LM Studio/mlx-lm | MTP projects | yes |

**Verdict for single-user, low-latency chat with tool calling:** at one user "the runtime is not the determining factor" once quantization is equalized. `llama-server` (or LM Studio wrapping it / MLX on a Mac) with `--jinja`, a Qwen3.6/Gemma 4 model with native MTP, `--cache-prompt`, and a modest KV quant is the pragmatic choice. SGLang is the upgrade for many constrained-JSON tool loops on CUDA; vLLM only if several household members hit it concurrently.

## 4. Agent frameworks and protocols

### 4.1 MCP status
- **Spec 2026-07-28:** stateless protocol core (no handshake/session IDs), first-class Extensions, Tasks for long-running work, MCP Apps (sandboxed HTML UIs), OAuth 2.0/OIDC hardening, routing headers, W3C Trace Context, formal deprecation policy, conformance suite.
- **Scale:** ~15,900 `mcp-server` GitHub repos (May 2026); ~71,000–101,000 servers across registries (Aug 2026); native clients: Claude, ChatGPT, Gemini, Copilot, Cursor.
- **Home Assistant:** built-in **MCP Server** integration (devices, areas, Assist intents) and **MCP client** integration; community `ha-mcp` offers 87 tools, read-only mode, per-tool enable/disable, predicate-based user-approval policies, automatic backups before edits. Since Sept 2025, OpenAI/Anthropic/Google/Ollama plug directly into Assist; reviewers report Qwen3 8B handling HA tool calls reliably.
- **Google Workspace:** official managed Workspace MCP servers rolling out from May 2026; community `taylorwilsdon/google_workspace_mcp` (120+ tools).
- **Browsers:** Microsoft **Playwright MCP** (accessibility tree, origin allow/block lists, isolated profiles); **browser-use** (114k stars, model-agnostic); Anthropic **Claude in Chrome** GA for paid plans with site-level permissions and mandatory confirmations for purchases/PII.

### 4.2 A2A
Linux Foundation project; v1.0.1 (May 2026); moved under the Agentic AI Foundation Aug 2026 (250+ members incl. Anthropic and OpenAI). Optional for a single household.

### 4.3 Frameworks

| Framework | Language | Notable for a Jarvis | Permission / HITL model |
|---|---|---|---|
| **Claude Agent SDK** | Python, TS | Same loop/tools/context management as Claude Code; MCP; subagents; sessions; hooks | Six-step evaluation: hooks → deny rules → ask rules → permission mode → allow rules → `canUseTool` callback; MCP tools can require user interaction; `PreToolUse` hooks always run |
| **OpenAI Agents SDK** | Python, TS | Handoffs, guardrails, sessions, tracing, realtime voice | Built-in HITL |
| **Pydantic AI** (19.9k stars) | Python | Model-agnostic (Anthropic, OpenAI, Google, Bedrock, Mistral, Ollama…), typed tools, MCP, A2A, OTel | **Deferred tools** = built-in human approval; durable execution via Temporal/DBOS |
| **LangGraph** (1.0 Oct 2025) | Python, JS | Graph state machines, checkpoints | Interrupt/resume nodes |
| **Google ADK** | Python, Java | Best on Google Cloud | — |
| **CrewAI**, **smolagents**, **Microsoft Agent Framework 1.0** | Python | Role crews / code-first agents | varies |
| **Claude Managed Agents** | REST | Anthropic hosts loop + sandbox; $0.08 per session-hour + tokens | server-side tool confirmations |

## 5. Long-term memory

| System | Architecture | Sourced numbers | Self-host / license |
|---|---|---|---|
| **mem0** | Multi-level (user/session/agent) vector + BM25 + entity + temporal; optional graph | Apr 2026 algorithm: LoCoMo 92.5, LongMemEval 94.4, p50 0.88 s | Apache 2.0; Docker Compose or cloud |
| **Zep / Graphiti** | Bi-temporal knowledge graph (facts have validity windows) | +15 points LongMemEval temporal reasoning [secondary] | Apache 2.0; Neo4j / FalkorDB; ships MCP server |
| **Letta (MemGPT)** | Self-editing core memory blocks + archival/recall; agent-as-server | Letta v1; Context Repositories (git-versioned memory, Feb 2026); TS SDK Aug 2026 | Apache 2.0 |
| **LangMem** | Background extraction/consolidation for LangGraph | — | open source |
| **Cognee** | Graph + vector memory API | €7.5M raise Feb 2026 | open source |
| **Anthropic memory tool** | Client-side `/memories` directory (view/create/str_replace/insert/delete/rename) + context editing + compaction | — | You own storage; enforce path-traversal protection |

**Vector stores:** Qdrant 12 ms p99 filtered ANN on 5M×768-d vs pgvector 34 ms; pgvector adequate under ~5M vectors and keeps data transactional; **LanceDB** is embedded (no server), columnar, multimodal — natural for a single-box assistant; Chroma for prototyping.

**Pattern:** (a) episodic log of raw interactions (timestamped, ideally bi-temporal), (b) semantic layer of extracted facts/preferences, (c) procedural memory (skills, instruction files). Personal data ingestion (email, calendar, notes, documents) via MCP servers feeding the same store; every reviewed memory paper warns about contamination from untrusted content.

## 6. Guardrails, permissions, safety for real-world actions

- Prompt injection is OWASP LLM01:2025 for the third year; **EchoLeak** (mid-2025) exfiltrated data from Microsoft 365 Copilot via an unopened email; five poisoned documents flipped RAG answers 90% of the time (Jan 2026); a Claude Chrome extension flaw allowed zero-click injection until a 19 Feb 2026 fix; NSA/CISA published an MCP security CSI (2 Jun 2026).
- Vendor mitigation: Claude for Chrome autonomous-mode attack success 23.6% → 11.2%; browser-specific attacks 35.7% → 0% [vendor-internal]. Anthropic's computer-use docs: run in a dedicated VM/container, allowlist domains, never hand raw credentials, require human confirmation for financial transactions.

**Recommended policy stack:**
1. **Tiered actions:** reads auto-approve; state-changing home calls allow-listed per entity; purchases, messages to third parties, deletes, and anything irreversible are `ask` rules routed to a confirmation channel. Never run a household agent in a permissions-bypass mode.
2. **Least privilege per MCP server:** ha-mcp read-only mode + per-tool enable; Playwright MCP origin allow-lists; Filesystem server scoped roots; memory tool path validation.
3. **Untrusted-content isolation:** treat email bodies, web pages and calendar descriptions as data; block tool calls that originate in a turn dominated by fetched content unless confirmed.
4. **Sandboxing:** browser/computer-use in a throwaway VM; code execution in containers.
5. **Audit:** log every tool call with arguments, source of triggering content, approver, and result; pre-edit backups give rollback.

## 7. Cost model: 200 interactions/day

Assumptions: 6,000 interactions/month; two model calls per interaction at ~4,000 input + ~300 output tokens each → **48M input, 3.6M output tokens/month**. Thinking tokens bill as output; Anthropic's new tokenizer inflates counts ≈30% vs 4.6-era estimates.

| Model | No caching | 75% of input as cache hits |
|---|---|---|
| Claude Haiku 4.5 ($1/$5) | $66 | ≈$34 |
| Claude Sonnet 5 ($2/$10) | $132 | ≈$67 |
| Claude Opus 5 ($5/$25) | $330 | ≈$168 |
| Claude Fable 5.1 ($10/$50) | $660 | ≈$309 |
| GPT-5.6 Luna ($0.20/$1.20) | $14 | — |
| GPT-5.6 Terra ($2/$12) | $139 | — |
| GPT-5.6 Sol ($5/$30) | $348 | — |
| Gemini 3.6 Flash ($0.75/$3.75) | $50 | — |
| Grok 4.6 ($2/$6) | $118 | — |
| DeepSeek V4 Flash API (off-peak) | ≈$13 | — |

Add-ons: web search $10/1,000 searches (≈$60/month at one search per interaction); computer/browser toolsets add 4.5–6.6K tokens per request — keep them out of the default tool list. **A Sonnet-5-default / Opus-5-escalation hybrid with caching lands around $70–150/month.** Local-only: zero per-token cost; capex + electricity (~200 W average ≈ 144 kWh/month ≈ $20 at $0.15/kWh — assumption). Break-even against a $100/month cloud bill is 2–4 years for a 128 GB box.

## 8. Recommendations

### (a) Cloud-first hybrid
- **Brain:** Claude Sonnet 5 as default turn model; escalate to Claude Opus 5 (effort medium–high) for multi-step planning; Haiku 4.5 (or GPT-5.6 Luna / Gemini 3.6 Flash) for classification/routing. Fable 5.1 is not worth 5x the price for a household assistant.
- **Harness:** Claude Agent SDK (Python) for its permission model, hooks and MCP support; or Pydantic AI for provider portability with deferred-tool approvals.
- **Tools:** MCP everywhere — HA MCP server or ha-mcp (read-only by default, approval predicates on writes), Google Workspace MCP, Filesystem, Fetch, Playwright MCP with origin allow-lists.
- **Memory:** Anthropic memory tool for procedural/working memory, plus mem0 (self-hosted) for semantic user facts and Graphiti for temporal episodic facts; server-side compaction for long sessions.
- **Local fallback:** Qwen3.6-35B-A3B or Gemma 4 12B on llama-server for intents and offline mode, and for pre-screening untrusted content.

### (b) Fully local
- **Hardware:** RTX 5090 for speed with models ≤32 GB; 128 GB unified-memory box (Strix Halo ≈ DGX Spark; Spark gets CUDA) for gpt-oss-120b / Mistral Small 4 / Gemma 4 31B Q8; 512 GB Mac Studio M5 Ultra (late Oct 2026) for DeepSeek V4 Flash / GLM-5.3-Flash class.
- **Models:** Qwen3.6-35B-A3B default; Gemma 4 26B-A4B or gpt-oss-120b alternates; DeepSeek V4.1 Flash or GLM-5.3-Flash if memory allows. Avoid Llama 4 (stale) and Kimi K3 / GLM-5.3 flagships (multi-GPU, restrictive licenses).
- **Server:** llama-server with `--jinja --spec-type mtp --cache-prompt`, JSON-schema constrained tool calls, avoid q4_0 KV cache; LM Studio/MLX on Macs.
- **Harness/memory:** Pydantic AI or LangGraph on the OpenAI-compatible endpoint; Letta or mem0 self-hosted with pgvector/LanceDB.
- **Safety:** same policy stack; local models are *more* susceptible to injection, so enforce approvals in the harness rather than relying on the model.

## Sources
- Anthropic: https://platform.claude.com/docs/en/about-claude/models/overview · https://platform.claude.com/docs/en/about-claude/pricing · https://platform.claude.com/docs/en/models/opus-5/overview · https://platform.claude.com/docs/en/models/sonnet-5/overview · https://platform.claude.com/docs/en/models/fable-5-1/overview · https://platform.claude.com/docs/en/build-with-claude/compaction · https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool · https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool · https://code.claude.com/docs/en/agent-sdk/overview · https://code.claude.com/docs/en/agent-sdk/permissions · https://techcrunch.com/2026/03/03/claude-code-rolls-out-a-voice-mode-capability/
- OpenAI / Google / xAI / Mistral (snippets): https://www.morphllm.com/openai-api-pricing · https://benchlm.ai/openai/api-pricing · https://openrouter.ai/google/gemini-3.6-flash · https://www.explainx.ai/blog/gemini-3-6-flash-3-5-flash-lite-cyber-launch-july-2026 · https://benchlm.ai/xai/api-pricing · https://mistral.ai/news/mistral-small-4/ · https://artificialanalysis.ai/models/comparisons/gemini-3-6-flash-vs-claude-sonnet-5-non-reasoning · https://github.com/openai/openai-agents-python · https://github.com/openai/gpt-oss
- Open-weight: https://openrouter.ai/qwen/qwen3.6-35b-a3b · https://unsloth.ai/docs/models/qwen3.6 · https://unsloth.ai/docs/models/mtp · https://insiderllm.com/guides/wicked-fast-qwen-3-6-27b-mtp-rtx-3090/ · https://www.morphllm.com/deepseek-v4 · https://ai.google.dev/gemma/docs/core/model_card_4 · https://deepinfra.com/blog/glm-5-1-model-overview · https://devoriales.com/kimi-k3-open-weights-what-moonshot-actually-shipped · https://codersera.com/blog/llama-4-complete-guide-2026/ · https://wavect.io/blog/open-weight-llm-comparison-2026/
- Hardware: https://float16.cloud/en-en/ai-benchmark/dgx-spark-vs-rtx-5090/ · https://presenc.ai/research/dgx-spark-vs-m5-max-vs-rtx-5090-throughput-2026 · https://verdictbits.com/reviews/dgx-spark-vs-strix-halo-vs-mac-studio/
- Inference servers: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md · https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md · https://insiderllm.com/guides/llamacpp-vs-ollama-vs-vllm/ · https://lmstudio.ai/blog/mlx-engine-agentic-workloads
- Protocols/frameworks: https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/ · https://github.com/modelcontextprotocol/servers · https://github.com/homeassistant-ai/ha-mcp · https://www.home-assistant.io/integrations/mcp_server/ · https://www.home-assistant.io/integrations/mcp/ · https://github.com/taylorwilsdon/google_workspace_mcp · https://github.com/microsoft/playwright-mcp · https://github.com/browser-use/browser-use · https://github.com/a2aproject/A2A · https://github.com/pydantic/pydantic-ai
- Memory: https://github.com/mem0ai/mem0 · https://mem0.ai/blog/state-of-ai-agent-memory-2026 · https://github.com/getzep/graphiti · https://github.com/letta-ai/letta · https://www.cognee.ai/best-ai-memory-layers-for-ai-agents-in-2026-comparison · https://4xxi.com/articles/vector-database-comparison/
- Safety: https://media.defense.gov/2026/Jun/02/2003943289/-1/-1/0/CSI_MCP_SECURITY.PDF · https://arxiv.org/pdf/2605.17634 · https://thehackernews.com/2026/03/claude-extension-flaw-enabled-zero.html · https://www.getmaxim.ai/articles/prompt-injection-defense-for-production-ai-agents-a-complete-2026-guide/
