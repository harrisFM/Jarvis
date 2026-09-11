# Jarvis — Research Summary and Build Plan for a State-of-the-Art Personal AI Assistant

**Status:** v1.0 · **Date:** 2026-09-11 · **Scope:** research findings and a complete build plan (hardware, software, integrations, security, cost, roadmap).

Supporting research notes with sources live in [`docs/research/`](research/). Every factual claim below is traceable to one of those notes; items the research could not verify against a primary source are marked **(uncertain)**.

**Contents:** [0. Executive summary](#0-executive-summary) · [1. Requirements](#1-what-jarvis-means-here-requirements-non-goals-success-metrics) · [2. Research findings](#2-what-the-research-found-and-what-to-design-against) · [3. Architecture](#3-target-architecture) · [4. Component decisions](#4-component-decisions) · [5. Hardware](#5-hardware-plan) · [6. Security and privacy](#6-security-privacy-and-permissions) · [7. Latency budget](#7-latency-budget-conversational-turn-prosumer-tier-local-speech--claude-sonnet-5) · [8. Cost model](#8-cost-model) · [9. Roadmap](#9-implementation-roadmap) · [10. Observability and evaluation](#10-observability-and-evaluation) · [11. Risks](#11-risks-uncertainties-and-open-questions) · [12. Appendix](#12-appendix)

---

## 0. Executive summary

"Build a Jarvis" content on YouTube and GitHub falls into three generations: (a) 2020–2024 Python scripts (blocking `speech_recognition` → rules/GPT → `pyttsx3`), (b) 2024–2026 Home Assistant + local-LLM builds (Voice Preview Edition, Whisper, Piper, Ollama), and (c) late-2025/2026 cloud speech-to-speech and agent builds (GPT-Realtime, LiveKit, Claude Code). All three share the same failure modes: multi-second latency, wake-word misfires, no echo cancellation so the assistant hears itself, Whisper hallucinating on silence, brittle tool calling on small models (37% task success measured on a local LLM through Home Assistant), no memory, single user, single room, and a one-year project half-life.

A state-of-the-art build in September 2026 is different in kind, not degree. The winning shape is:

- **Room satellites with hardware echo cancellation** (XMOS-based: Home Assistant Voice PE $59, FutureProofHomes Satellite1 ~$135, ReSpeaker XVF3800) running an on-device wake word, streaming audio to one household "brain".
- **A streaming cascade** (wake word → VAD + audio end-of-turn model → streaming STT → LLM → sentence-chunked streaming TTS) orchestrated by **Pipecat 1.9** (BSD-2, self-hosted, Smart Turn v3.2 end-of-turn on CPU, MCP client, OpenTelemetry). Realistic target: **600–900 ms** end-of-speech to first audio, versus 3–5 s in typical tutorials.
- **Local speech, tiered brain.** Raw audio never leaves the house: NVIDIA Nemotron/Parakeet streaming STT and Qwen3-TTS run on the home GPU. The brain is tiered: a local model (Qwen3.6-35B-A3B or gpt-oss-120b) for device control and offline fallback, **Claude Sonnet 5** as the default conversational/agentic model, **Claude Opus 5** for hard multi-step tasks. Optional "chatty mode" via a native speech-to-speech model (gpt-realtime-2.1-mini or Gemini 3.1 Flash Live).
- **Home Assistant as the device and intent hub, not the brain**, exposed to the agent through its built-in MCP server; Music Assistant + Sendspin/Snapcast as the whole-home audio bus.
- **MCP for every tool** (Home Assistant, Google Workspace, filesystem, browser via Playwright MCP), **mem0 + Graphiti** for semantic and temporal memory, and a **permission harness** (Claude Agent SDK permission rules or Pydantic AI deferred tools) with tiered approvals, because prompt injection through email and web content is a demonstrated attack class.
- **Hardware:** a low-idle 128 GB unified-memory box is the sweet spot for a 24/7 single-conversation household: **NVIDIA DGX Spark-class ($3,699–4,699, 22–25 W idle, ~40–60 tok/s on gpt-oss-120b)** or **AMD Strix Halo ($2,000–3,450, 12.5 W idle, ~31–34 tok/s)**. Discrete RTX 5090 is faster but cannot hold 120B-class models and idles hot; Mac Studio M5 Ultra (512 GB, ships late Oct 2026) is the no-compromise pick for the largest open models but is weak at prompt processing.

**Recommended configuration (prosumer tier, ~$4,500–6,500 hardware, ~$70–150/month API):** DGX Spark partner box or Strix Halo mini PC + 4–6 XMOS satellites + Intel N150 Frigate box + presence sensors + PoE/VLAN networking + UPS; Pipecat brain in Docker; Home Assistant OS on the same host or a separate mini PC; Claude Sonnet 5/Opus 5 hybrid with local Qwen3.6 fallback. Full details in sections 4–8 and the phased roadmap in section 9.

---

## 1. What "Jarvis" means here: requirements, non-goals, success metrics

### 1.1 Functional requirements
1. **Natural voice conversation anywhere in the home**: wake word ("Jarvis"), continued conversation without re-waking, barge-in (interrupt while it speaks), room awareness ("turn on the lights" means this room).
2. **Reliable home control** through Home Assistant: lights, climate, locks, media, vacuum areas, timers, announcements, scenes — with deterministic intent handling for common commands and LLM reasoning for everything else.
3. **Personal agent**: calendar, email triage and drafting, reminders/to-dos, web research with citations, news and weather briefings, travel/traffic, shopping lists, document Q&A over personal files, code and computer tasks on request.
4. **Memory**: remembers people, preferences, past decisions, and what was true when; per-person profiles via speaker identification.
5. **Proactive behavior**: morning briefing, leaving-home checks, calendar conflicts, package delivered, anomaly alerts from cameras/sensors — rate-limited and quiet-hours aware.
6. **Multi-modal input**: cameras (presence, "who is at the door", "did I leave the garage open"), phone/desktop clients with live transcript, optional phone-call access.
7. **Multi-user**: household members recognized by voice, guests handled with reduced permissions, children with restricted actions.
8. **Works offline** for home control and basic conversation when the internet or a cloud provider is down.

### 1.2 Non-functional requirements
- **Latency:** end-of-speech to first audio p50 ≤ 800 ms, p95 ≤ 1,200 ms for conversational turns; device-control intents ≤ 500 ms via the local fast path.
- **Wake word:** < 0.5 false accepts per hour per room; < 5% false rejects at 3–5 m in a quiet room.
- **Task success:** ≥ 95% on a scripted home-control eval set; ≥ 85% on a personal-agent eval set (calendar, email, research).
- **Privacy:** raw audio never leaves the LAN; only transcripts and tool results go to cloud LLMs, under zero-data-retention or 30-day retention terms as the provider allows; a hardware mute exists in every room.
- **Safety:** every irreversible or outward-facing action (purchases, sending messages, unlocking doors, deleting data) requires explicit confirmation; every tool call is audited.
- **Availability:** the pipeline recovers automatically from any single process crash; satellites reconnect; degraded mode when a cloud provider fails.
- **Cost:** ≤ $150/month opex at ~200 interactions/day.

### 1.3 Non-goals (v1)
- Human-indistinguishable full-duplex speech (Moshi-style) — no open model does tool calling reliably yet.
- Autonomous purchases or money movement without confirmation.
- Public-internet exposure of the assistant; remote access is via VPN/tunnel only.
- Supporting non-household users at scale.

---

## 2. What the research found (and what to design against)

The five research notes converge on a short list of lessons:

| Lesson | Evidence | Design response |
|---|---|---|
| Non-streaming pipelines are the #1 cause of "Jarvis feels slow" | Tutorials report 1–2 s on an RTX 3060, 5–8 s on a Pi 5, 15–45 s on CPU; Voice PE reviews measured 3.9–5.2 s | Stream every stage; sentence-chunk LLM output into TTS; use an end-of-turn model instead of fixed silence timeouts |
| Software-only mics cannot do barge-in | isair/jarvis loses "stop" commands to its own echo filter; Voice PE needs the wake word twice to interrupt | XMOS hardware AEC on every satellite; WebRTC AEC3 + DeepFilterNet only as a fallback |
| Wake-word models are fragile across firmware updates | HA core issues #157932, #165860, #167989, #167259 (2024.12–2026.4 regressions) | Pin satellite firmware; stage updates on one satellite first; keep a hub-side openWakeWord fallback |
| Whisper hallucinates on silence/noise | isair #147, Willow #340 | Use streaming-native ASR (Nemotron/Parakeet/Kyutai) with VAD gating and confidence filtering |
| Small local models fail at tool calling | 37% task success (local) vs 58% (cloud) in Voice PE tests; HA issues #167154, #177156, #177965 | Deterministic intents for common commands; frontier model for agentic work; strict JSON schema tool calls; verify tool results, never trust "success" text |
| No memory, no multi-user | No surveyed project does speaker ID; GLaDOS #182, #218 | mem0 + Graphiti memory; ECAPA-TDNN speaker ID per utterance; per-user profiles and permissions |
| Prompt injection is real, not theoretical | EchoLeak (M365 Copilot, 2025); Claude Chrome extension zero-click fix Feb 2026; NSA/CISA MCP CSI June 2026 | Tiered permissions in the harness, not in the prompt; untrusted-content isolation; browser in a throwaway VM |
| Projects die within a year | 01, June, RealtimeVoiceChat, Willow releases, rhasspy3, wyoming-satellite all dormant/archived | Build on the two frameworks with 2026 releases and >14k stars (Pipecat, LiveKit), on Home Assistant, and on open protocols (MCP, Wyoming/ESPHome) |
| Speech-to-speech is faster but less controllable | Cascades give provider choice, visible transcripts, guardrails on text, swappable local LLM; S2S re-bills context audio each turn | Cascade as primary; S2S as an optional mode for open-ended chat |
| Hardware: bandwidth, not FLOPs, sets decode speed; idle power sets the electricity bill | DGX Spark 273 GB/s; Strix Halo ~256 GB/s; Mac 614–800+ GB/s; RTX 5090 1.79 TB/s but 32 GB; Spark 22–25 W idle vs 5090 desktop 40–80 W | Prefer MoE models (gpt-oss-120b, Qwen3.6-35B-A3B); pick a low-idle unified-memory box for 24/7 |

---

## 3. Target architecture

```
                         ┌─────────────────────── Rooms ────────────────────────┐
                         │  Satellite (Voice PE / Satellite1 / XVF3800 + ESP32) │
                         │  XMOS AEC/beamform → microWakeWord → PCM stream      │
                         │  Speaker (Sendspin/Snapcast group)  Presence sensor  │
                         └───────────────┬───────────────────────▲──────────────┘
                                         │ ESPHome/Wyoming (IoT VLAN)            │ TTS audio, announcements
                                         ▼                                       │
┌───────────────────────────────── Home GPU server (24/7) ────────────────────────┴──────────────────┐
│                                                                                                    │
│  ┌──────────────── Voice pipeline (Pipecat 1.9, one process per household) ───────────────────┐    │
│  │  Silero VAD → Smart Turn v3.2 (EOU) → Streaming STT (Nemotron-3.5 / Parakeet, local GPU)   │    │
│  │  → Speaker ID (ECAPA-TDNN) → Context assembly (room, speaker, HA state, memory recall)     │    │
│  │  → Router → LLM (streaming) → sentence chunker → Streaming TTS (Qwen3-TTS local /          │    │
│  │    Cartesia Sonic 3.5 cloud) → barge-in controller (cancel TTS, flush LLM on VAD onset)     │    │
│  └────────────────────────────────────────┬───────────────────────────────────────────────────┘    │
│                                           │ text turns + tool calls                                │
│  ┌──────────────── Brain (agent harness: Claude Agent SDK / Pydantic AI) ──────────────────────┐   │
│  │  Tier 0  Deterministic intents (HA "prefer local", Speech-to-Phrase grammar)  ≤ 300 ms     │   │
│  │  Tier 1  Local LLM  (llama-server: Qwen3.6-35B-A3B / gpt-oss-120b)  control, offline       │   │
│  │  Tier 2  Claude Sonnet 5  default conversation + tools  (thinking off / low effort)         │   │
│  │  Tier 3  Claude Opus 5   multi-step planning, research, code  (effort medium–high)          │   │
│  │  Opt.    gpt-realtime-2.1-mini / Gemini 3.1 Flash Live  "chatty" speech-to-speech mode      │   │
│  │  Permission engine: allow / ask / deny rules per tool + per user; audit log; injection      │   │
│  │  isolation for fetched content; confirmation channel (voice, phone push)                    │   │
│  └───────┬───────────────────────────┬─────────────────────────────┬───────────────────────────┘   │
│          │ MCP                        │ MCP                         │ memory API                   │
│  ┌───────▼────────┐   ┌───────────────▼──────────────┐   ┌──────────▼──────────────┐              │
│  │ Home Assistant │   │ Personal tools (MCP servers)  │   │ Memory                  │              │
│  │ MCP server     │   │ Google Workspace, Filesystem, │   │ mem0 (semantic facts)   │              │
│  │ (entities,     │   │ Fetch/Search, Playwright      │   │ Graphiti (temporal KG)  │              │
│  │ areas, intents)│   │ (sandboxed VM), Music Asst.,  │   │ LanceDB/pgvector docs   │              │
│  └───────┬────────┘   │ Frigate, Telegram/Signal…     │   │ episodic transcript log │              │
│          │            └───────────────────────────────┘   └─────────────────────────┘              │
│  ┌───────▼──────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ Home Assistant OS/Container: devices (Zigbee/Z-Wave/Matter/Thread), automations, timers,     │  │
│  │ announcements, Assist pipelines (fallback), Music Assistant, Frigate (N150/OpenVINO box)      │  │
│  └──────────────────────────────────────────────────────────────────────────────────────────────┘  │
│  Observability: OpenTelemetry → Langfuse (self-hosted) + Prometheus/Grafana; eval harness         │
└────────────────────────────────────────────────────────────────────────────────────────────────────┘
          ▲ Tailscale / Cloudflare Tunnel (Zero Trust)              ▲ optional SIP/Twilio
   Phone & desktop clients (HA Companion, PWA with live transcript, Linux voice assistant)
```

Key properties:
- **One brain, many ears.** Satellites are dumb, cheap, and replaceable; all intelligence and state live on the server.
- **Text is the contract.** Every stage exchanges text plus metadata (room, speaker, timestamps), so any component can be swapped, logged, evaluated, and guarded.
- **Fast path first.** Deterministic intents handle the 60–80% of utterances that are device commands in under half a second and cost nothing; the LLM tiers handle the long tail.
- **Cloud is optional per turn.** The router decides per turn whether a local or cloud model runs; when cloud is unreachable the system degrades to Tier 0/1 automatically.

---

## 4. Component decisions

Each subsection gives the primary choice, the alternative, and the fully-local fallback, with the reasoning from the research notes.

### 4.1 Room satellites (ears and mouth)

| Role | Primary | Alternative | Notes |
|---|---|---|---|
| Standard room | **Home Assistant Voice Preview Edition** ($59; ESP32-S3 + XMOS XU316 2-mic AEC/NS/AGC/beamforming; microWakeWord; 3.5 mm out; Sendspin multi-room) | **FutureProofHomes Satellite1** (~$135 assembled; 4-mic XMOS array, 25 W amp, temp/humidity/lux/presence sensors) | Only buy XMOS-equipped hardware. ESP32-S3-BOX-3 and Atom Echo lack a DSP and degrade in noisy rooms. |
| Large/noisy room | **Seeed ReSpeaker XVF3800 + XIAO ESP32-S3** (4-mic circular, 5 m 360° pickup, DoA, dereverb; ~$60) | Raspberry Pi 5 + ReSpeaker USB Mic Array (XVF3000) running OHF linux-voice-assistant | Pi route gives hub-side openWakeWord and wired Ethernet/PoE. |
| Desk / office | **OHF-Voice linux-voice-assistant** on the desktop (ESPHome protocol, auto-discovered by HA) | Browser PWA client (WebRTC to Pipecat) | Free; gives a screen for transcripts and confirmations. |
| Wearable / mobile | HA Companion app (Android as default assistant; on-device microWakeWord since 2026.3) | iOS Shortcuts → Assist; PWA | No usable smart-glasses developer path found for a private assistant **(uncertain)**. |
| Output | Satellite speaker for short replies; **Music Assistant + Sendspin/Snapcast** group for music and announcements with pre-announce chime and volume ducking | Sonos/Cast via Music Assistant | Announcements target `assist_satellite` or MA players. |

Firmware policy: pin Voice PE/ESPHome versions; upgrade one satellite first; keep the hub-side openWakeWord path as a fallback because microWakeWord regressions have shipped four times since 2024.12.

### 4.2 Wake word, VAD, turn detection, echo cancellation

| Function | Choice | Why |
|---|---|---|
| Wake word (on device) | **microWakeWord** custom "Jarvis" model trained from synthetic (Piper/TTS) data; openWakeWord "hey_jarvis" on Linux satellites | Free, Apache-2.0, on-device on ESP32-S3; targets <0.5 FA/h, <5% FR. Picovoice Porcupine is the least-tuning commercial option (>97% detection, <1 FA/10 h claimed) but commercial licensing is sales-led **(uncertain)**. |
| Frame VAD | **Silero VAD v6.2** (MIT, 1.2 MB, 32 ms chunks) | De-facto standard in Pipecat and LiveKit. |
| End of utterance | **Pipecat Smart Turn v3.2** (BSD-2, 8 MB int8, 10–100 ms on CPU, 23 languages) | Semantic "done or thinking?" decision instead of fixed silence; removes 300–800 ms of dead air; runs on CPU. Alternative: Deepgram Flux (cloud ASR with integrated end-of-turn). |
| Barge-in | VAD onset during TTS → cancel TTS → flush LLM stream; only works with hardware AEC | This is exactly where every DIY build fails. |
| AEC / NS | In silicon (XMOS). Hub-side fallback: WebRTC AEC3 then DeepFilterNet3 (one AEC, one NS, AEC first, never stack suppressors) | |
| Continued conversation | Keep mic open for N seconds after an answer; end on Smart Turn "complete" + silence | HA Voice Chapter 10 pattern. |

### 4.3 Speech-to-text

| Mode | Choice | Numbers |
|---|---|---|
| **Primary (local)** | **NVIDIA Nemotron-3.5-ASR-Streaming-0.6B** (June 2026, Apache-2.0, 40 languages, cache-aware, 80 ms–1 s chunks); **Parakeet-unified-en-0.6b** for English-only (160 ms minimum latency) | Parakeet-TDT tops the Open ASR leaderboard (~6.05% WER vs 7.44% Whisper-v3); ~30x real-time on CPU INT8; needs ~2–4 GB VRAM on the GPU box |
| Higher accuracy (local) | Mistral Voxtral Realtime 4B (Apache-2.0, sub-200 ms configurable) | Needs 16 GB+ VRAM |
| Cloud alternative | ElevenLabs Scribe v2 Realtime (~150 ms, 90+ languages) or AssemblyAI Universal-3 Pro Streaming (built-in diarization); Deepgram Flux for ASR + end-of-turn in one stream ($0.0065/min) | Only if you accept audio leaving the LAN |
| Deprecated | Chunked Whisper (faster-whisper/whisper.cpp) | Hallucination on silence; no native streaming; keep as a last-resort offline fallback on CPU-only boxes |

Speaker identification: **SpeechBrain ECAPA-TDNN** embeddings computed on each wake-word utterance, cosine-matched against enrolled household voiceprints (Apache-2.0, CPU); pyannote 4 community-1 only for multi-party transcripts. Cloud speaker-ID is disappearing (Azure retired Sept 2025, Amazon Voice ID exited May 2026).

### 4.4 Text-to-speech

| Mode | Choice | Numbers |
|---|---|---|
| **Primary (local)** | **Qwen3-TTS-1.7B** (Jan 2026, Apache-2.0, 10 languages, ~97 ms first packet, 3-second voice cloning) | Best quality/latency/license combination found; ~4–6 GB VRAM **(uncertain)** |
| Lighter local | Chatterbox Turbo 350M (MIT, <200 ms, watermarked) on small GPU; Kyutai Pocket TTS 100M (MIT) or Kokoro-82M (Apache-2.0) on CPU-only | Kokoro-wyoming streams "before the LLM finishes" in HA |
| **Cloud (best voice)** | **Cartesia Sonic 3.5** (measured ~166–190 ms p50 TTFA, streaming, cloning); ElevenLabs Flash v2.5 as second provider (measured ~288 ms) | Eleven v3 only for non-interactive narration |
| Legacy | Piper (piper1-gpl, GPL-3.0, seeking maintainers) | Fine on Pi-class satellites; not the primary voice |

Voice design: one consistent cloned/persona voice; sentence-level streaming; short spoken sentences; no markdown or lists in speech; distinct earcons for wake, thinking, confirmation-needed, and error.

### 4.5 Orchestration framework

**Primary: Pipecat 1.9 (BSD-2, Python).** Reasons from note 05: fully self-hostable; Smart Turn v3.2 runs on CPU; MCP client built in (1.8); local Whisper/Kokoro/PocketTTS/Ollama services; SmallWebRTC transport (no cloud account); per-turn OpenTelemetry spans with TTFB and latency breakdown (1.9); telephony serializers if needed; 15k+ stars with releases in the same week as this document.

**Alternative: LiveKit Agents 1.8 (Apache-2.0)** if you want a WebRTC SFU for many simultaneous clients or native SIP; note that the best turn-detection model is cloud-only and self-hosters run the v1-mini CPU model.

**Rejected as the core:** Vapi/Retell/Bland/ElevenLabs Agents/Deepgram Voice Agent (hosted, phone-first, per-minute pricing unsuitable for an always-on mic); Vocode (dormant since Nov 2024); Home Assistant's own Assist pipeline as the *brain* (kept as the device hub and as a fallback pipeline).

Satellite ingress: satellites speak ESPHome/Wyoming to Home Assistant. Two integration options, both keep HA's fast path:
1. **HA-fronted:** HA runs the Assist pipeline with local wake/STT and "prefer handling commands locally"; non-intent utterances are forwarded to the Pipecat/agent service through a custom conversation agent (OpenAI-compatible endpoint — HA 2026.8 added an OpenAI-compatible/llama.cpp agent). Simplest; leverages HA area resolution and continued conversation.
2. **Pipecat-fronted:** a small Wyoming/ESPHome bridge streams satellite audio straight into Pipecat, which calls HA intents via MCP. More control over turn-taking and barge-in; more code.

The roadmap starts with option 1 (Phase 2) and moves to option 2 (Phase 3) once the pipeline is stable.

### 4.6 The brain: LLM tiering

| Tier | Model | Used for | Latency / cost |
|---|---|---|---|
| 0 | Home Assistant intents + Speech-to-Phrase grammar | "turn off the kitchen lights", timers, media, scenes | <300 ms, $0 |
| 1 | **Local: Qwen3.6-35B-A3B** (Apache-2.0; 35B/3B active; SWE-bench Verified 73.4) or **gpt-oss-120b** (Apache-2.0, ~60 GB MXFP4) on `llama-server` | Device control with ambiguity, short chit-chat, offline mode, pre-screening untrusted email/web text | 40–100 tok/s on a 128 GB box; $0 |
| 2 | **Claude Sonnet 5** (`claude-sonnet-5`; $2/$10 per MTok; 1M context; "Fast"; 0.97 s TTFT with thinking off) | Default conversational and agentic turns with tools | ~$67–132/month at 200 turns/day |
| 3 | **Claude Opus 5** (`claude-opus-5`; $5/$25; effort medium–high) | Multi-step planning, research synthesis, code, anything the router flags as hard | Escalation only; ~10–20% of turns |
| S2S | gpt-realtime-2.1-mini (≈$0.016–0.05/min) or Gemini 3.1 Flash Live (proactive audio, affective dialog) | Optional "conversation mode" for open-ended chat, language practice, kids' stories | Only when explicitly invoked; audio leaves LAN |

Router: a Haiku 4.5 (or local 3B) classifier plus heuristics (tool count, presence of fetched content, user request for "think hard") picks the tier. Claude Fable 5.1 ($10/$50) is not worth 5x Opus for a household assistant; keep it available behind an explicit "deep think" request.

Provider portability: everything goes through the agent harness, so OpenAI GPT-5.6 Terra/Sol or Gemini 3.1 Pro can be swapped in per tier. Anthropic has no audio-in API, which is why the speech layer is separate.

Prompting for voice: short spoken sentences, no markdown, explicit tool-result verification ("only claim success after the tool result says so"), room and speaker context injected as a mid-conversation system message to preserve prompt caching, and a stable system prompt/tool list first for cache hits (cache reads are 10% of input price).

### 4.7 Agent harness and tools (MCP)

**Harness:** **Claude Agent SDK (Python)** for its six-step permission evaluation (hooks → deny → ask → mode → allow → `canUseTool`), MCP support, subagents, sessions and hooks; **Pydantic AI** is the provider-portable alternative with built-in "deferred tools" for human approval and OpenTelemetry. Never run the household agent in a permissions-bypass mode.

**MCP tool catalogue (Phase-ordered):**

| Domain | Server | Notes |
|---|---|---|
| Home | **Home Assistant MCP Server** integration (`/api/mcp`, OAuth/long-lived token) or community **ha-mcp** (87 tools, read-only mode, per-tool enable, approval predicates, pre-edit backups) | Keep exposed entities lean (<25 for local models) or use mcp-assist on-demand discovery (~400 tokens vs 12,000+) |
| Calendar / email / docs | Google's official Workspace MCP servers (rolling out since May 2026) or `taylorwilsdon/google_workspace_mcp` (120+ tools); `Softeria/ms-365-mcp-server` for Microsoft 365 | Email bodies are untrusted content |
| Files / notes | MCP Filesystem (scoped roots), Obsidian/Markdown vault, LanceDB doc index | |
| Web | Provider-side web search (Anthropic $10/1k searches) for zero plumbing; Brave ($5/1k), Exa ($7/1k), Tavily, Perplexity Sonar as alternatives | Fetched pages are untrusted content |
| Browser / computer | **Playwright MCP** (accessibility tree, origin allow-lists, isolated profile) inside a throwaway VM; Anthropic computer-use/browser toolsets only when needed (they add 4.5–6.6k tokens per request) | Purchases and logins always require confirmation |
| Music | Music Assistant (2.10.x) via HA; Spotify MCP is inactive | |
| Cameras | Frigate (0.17/0.18) via HA/MQTT: events, snapshots, GenAI descriptions, semantic search | |
| Messaging | Telegram MCP / Signal MCP (signal-cli) preferred; WhatsApp MCP is unofficial with ban risk | Sending is an "ask" action |
| Dev | GitHub official MCP; Claude Code sessions via Agent SDK | |
| Telephony (optional) | HA `voip` + Grandstream HT801, community VoIP Stack 2026.9, or OpenAI Realtime SIP attach | |

### 4.8 Memory

Three layers, all self-hosted:
1. **Episodic log:** every turn (room, speaker, transcript, tool calls, results) in Postgres; retention policy per user; searchable by the assistant with time filters.
2. **Semantic facts and preferences:** **mem0** (Apache-2.0; Apr 2026 algorithm: LoCoMo 92.5, LongMemEval 94.4, p50 0.88 s) on **pgvector** (adequate under 5M vectors, transactional) or **LanceDB** (embedded, no server) for documents.
3. **Temporal knowledge graph:** **Graphiti/Zep** (Apache-2.0, bi-temporal facts with validity windows, ships an MCP server) for "what was true in March" and relationships between people, places, devices and events. Requires a model that produces structured output reliably — test Qwen3.6 first, otherwise use Sonnet 5 for extraction.
4. **Procedural memory:** Anthropic memory tool (`/memories` directory with strict path validation) for the assistant's own notes, plus versioned instruction files (persona, house rules, per-room defaults) in this repo.

Memory writes from untrusted content (emails, web pages) are quarantined and require confirmation before becoming facts, because five poisoned documents flipped RAG answers 90% of the time in a Jan 2026 study.

### 4.9 Home Assistant's role

Home Assistant stays the system of record for devices, areas, users, automations, timers and announcements:
- Entity exposure and aliases curated for voice; areas mapped to satellites.
- "Prefer handling commands locally" and Speech-to-Phrase for the fast path.
- Timers, `assist_satellite.announce` and `start_conversation` for proactive behavior; 2026.5 timer lifecycle triggers and volume conditions for quiet hours.
- MCP Server integration exposes the Assist API to the brain; MCP client integration lets HA's own agents use external tools as a fallback pipeline.
- Music Assistant for whole-home audio; Frigate for cameras; Matter Server on matter.js (Matter 1.5.1) for Matter/Thread devices.
- Note the 2026.9 breaking change: LLM tool names are domain-prefixed (`intent__HassTurnOn`).

### 4.10 Vision and presence ("eyes")

| Capability | Choice | Why |
|---|---|---|
| Camera detection, faces, plates, search | **Frigate 0.17/0.18** on an Intel N150 box with OpenVINO (Hailo-8 when scaling): object detection, face recognition (ArcFace on GPU/NPU; 20–30 enrolment images per person; thresholds 0.7/0.8/0.9), LPR, semantic search (Jina CLIP), GenAI review summaries returning structured JSON with `confidence` and `threat_level` | Verified in Frigate docs; the structured fields are natural gates for proactive alerts; Coral cannot accelerate these enrichments |
| Local scene description / camera Q&A | **Qwen3-VL** (Apache-2.0; 8B or 30B-A3B) or **Gemma 4** via llama.cpp `--mmproj` on the brain box | Frigate's own recommendation; keeps images local |
| "Look at this" from a phone or glasses | Sonnet 5 vision (image input is native) for hard questions; Gemini 3.1 Flash Live at 1 fps only when the user explicitly asks it to watch | Cloud vision is opt-in per request |
| Presence | mmWave sensors per room (Everything Presence Lite/One, Aqara FP2) + satellite state | Gates proactive speech; drives room-aware routing |
| Wearable HUD (optional, Phase 6) | **MentraOS** (Apache-2.0) on Even Realities G2 / Mentra Live / Vuzix Z100, or Brilliant Labs Halo | Open SDK with mic, camera, display; Meta Ray-Ban Display's third-party toolkit is a developer preview with undated GA and unclear assistant replacement **(uncertain)** |

Face and voice recognition are biometric processing: enrolment is explicit and per person, guests are never enrolled, and a guest mode disables recognition (see section 6).

### 4.11 Clients and access

| Surface | Implementation |
|---|---|
| Rooms | Satellites (4.1) |
| Desktop | OHF linux-voice-assistant (wake word, ESPHome protocol) + a **web dashboard/PWA** served by the brain: live transcript, tool-call log, pending confirmations (accept / edit / deny), memory browser, per-user settings |
| Phone | Home Assistant Companion (Android: default assistant app, on-device microWakeWord since 2026.2.3; iOS: Siri Shortcut → Assist, noting the default-agent limitation in core #108503); the PWA over Tailscale for transcripts and confirmations; push notifications for approvals |
| Phone call (optional) | Home Assistant `voip` + Grandstream HT801, the community VoIP Stack (2026.9), or OpenAI Realtime SIP attach |
| Remote access | **Tailscale** (or Cloudflare Tunnel behind Zero Trust); nothing on the public internet |
| Messaging | Telegram/Signal bot for text conversations and approvals when away |

### 4.12 Proactive behavior (ambient agent)

Pattern (from LangChain's ambient-agents design and Home Assistant's satellite APIs): every event is **triaged** into ignore / notify / respond; only "notify" and "respond" reach a human, and "respond" actions go through the approval inbox.

- **Event sources:** HA state changes (door, garage, leak, power), Frigate review summaries (`threat_level` ≥ 1, `confidence` ≥ 0.7), calendar (next event in 30 min, conflicts, travel time), email (flagged senders), package delivery, weather alerts, device health (battery, offline), memory-derived reminders.
- **Delivery:** `assist_satellite.announce` (pre-announce chime, 20 dB ducking) in the room where presence is detected and the satellite is `idle`; `start_conversation` with `extra_system_prompt` when a reply is useful ("Your 3 pm moved to 4; should I tell Alex?"); phone push when nobody is home; `ai_task.generate_data` for the morning briefing (calendar, weather, commute, news, overnight camera events).
- **Anti-annoyance rules:** notification classes with fixed importance levels the household can edit; quiet hours; per-class daily caps; no speaking when a conversation is in progress; a "why did you say that" log; never escalate silently.
- **Scheduling:** HA time/state/timer triggers for home events; the agent harness's own scheduler (or Claude Code Routines-style cron) for personal-agent jobs like inbox triage.

---

## 5. Hardware plan

### 5.1 Central server ("the brain")

Physics first: single-conversation decode speed is bounded by memory bandwidth; prefill (reading long tool-heavy prompts) is compute-bound; 24/7 cost is set by idle power. That rules the choice.

| Option | Price (Sept 2026) | Fits | Measured decode | Idle | Verdict |
|---|---|---|---|---|---|
| **NVIDIA DGX Spark class** (GB10, 128 GB, 273 GB/s): ASUS Ascent GX10 from $3,999; Dell Pro Max GB10 $3,699–3,999; Founders $4,699 | $3,699–4,699 | gpt-oss-120b, Qwen3.6-35B-A3B, Mistral Small 4, Gemma 4 31B Q8 + STT/TTS resident | gpt-oss-120b 39–61 tok/s (runtime-dependent), prefill ~1,200–1,956 tok/s; Qwen3-30B MoE 89 tok/s; dense 70B only 3–7 tok/s | 22–25 W (after firmware fix) | **Recommended prosumer pick**: CUDA for Nemotron/Parakeet/Qwen3-TTS, best prefill of the unified-memory boxes |
| **AMD Strix Halo** (Ryzen AI Max+ 395, 128 GB): GMKtec EVO-X2 ~$1,999 promo–$2,799; Framework Desktop $3,449; HP Z2 Mini G1a ~$3,300 | $2,000–3,450 | same model set | gpt-oss-120b 31–34 tok/s; Qwen3-30B-A3B 70–100 tok/s | 12.5 W | **Value pick**; Vulkan/ROCm stack less mature than CUDA for speech models; prefill figures unverified **(uncertain)** |
| **Apple Mac Studio M5 Max** 128 GB (614 GB/s) / **M5 Ultra** up to 512 GB (announced 25 Aug 2026; GA 22 Sept; 512 GB late Oct) | from $2,499 / from $5,499 (512 GB likely ~$9–10k, uncertain) | M5 Ultra 512 GB: DeepSeek V4 Flash / GLM-5.3-Flash / 671B-class MoE Q4 | M3 Ultra ran DeepSeek 671B 4-bit at >20 tok/s (MLX); M5 not yet benchmarked | ~9–10 W | **No-compromise for model size and silence**; weak prompt processing (~400 tok/s on 8B for M5 Max) hurts long tool prompts; no CUDA (MLX/CoreML for speech) |
| **RTX 5090** 32 GB in a desktop | GPU alone $5,069–5,799 (2.5x MSRP) | ≤32 GB models: Qwen3.6-27B/35B-A3B, Gemma 4 26B, gpt-oss-20b | 2.7–4x faster than unified boxes on what fits; 205 tok/s gpt-oss-20b | 30–46 W GPU + host; 575 W peak; 38–42 dBA | Fastest for mid-size models; cannot run 120B class; loud and hot for 24/7 |
| **RTX PRO 6000 Blackwell** 96 GB (Max-Q 300 W) | $7,999–9,449 + host | gpt-oss-120b at full speed, 70B Q8 | fastest single card | 60–100 W system | Top-end discrete option |
| **Used RTX 3090** 24 GB in an existing PC | $700–1,050 | Qwen3.6-27B Q4 (~60 tok/s with MTP), gpt-oss-20b, STT/TTS | fast | ~30 W GPU + host | **Budget pick** |
| Intel Arc Pro B60 24 GB | $660–800 | ~38B Q4 | comparable (vendor claim) | — | Budget alternative; less mature stack |
| Cloud GPU rental (RTX 5090 24/7) | $108–382/month | anything | — | — | $3,000–4,600/yr; only wins below ~1/3 utilization and sends transcripts off-site |

**Decision:** DGX Spark-class for the recommended build (CUDA ecosystem for every speech model in section 4, 128 GB for a 120B-class MoE plus STT/TTS/embeddings resident, ~23 W idle ≈ $35/yr electricity). Strix Halo if budget matters more than prefill speed and CUDA. Mac Studio M5 Ultra if the goal is the largest open models at near-silent operation and you accept MLX-only speech tooling. Avoid dense 70B models on any unified-memory box.

VRAM budget on a 128 GB box (approximate): LLM 60–70 GB (gpt-oss-120b MXFP4) or ~20 GB (Qwen3.6-35B-A3B Q4) · STT 2–4 GB · TTS 4–6 GB · embeddings + speaker ID 1–2 GB · KV cache and headroom 20+ GB.

### 5.2 Home Assistant and services host
Run Home Assistant OS in a VM (Proxmox) or HA Container on the same box, or on a separate fanless mini PC for isolation and uptime during GPU-box maintenance. Frigate runs best on an **Intel N100/N150 mini PC ($309–339) with OpenVINO** for 2–6 cameras (Coral is reported end-of-life for new installs **(uncertain)**; Hailo-8/8L when scaling). Proxmox LXC GPU passthrough is the preferred way to share one GPU across llama-server, STT/TTS and Frigate if they co-locate.

### 5.3 Satellites, sensors, displays
- 4–6 × Home Assistant Voice PE ($59) and/or 2 × Satellite1 (~$135) for main rooms; XVF3800 kit for the largest room; linux-voice-assistant on desktops.
- Presence: Everything Presence Lite ($34–38) / One ($57–64) or Aqara FP2 ($58–83) per room for room-aware routing and proactive logic.
- Displays: Inkplate 10 / TRMNL X e-ink for ambient briefings; jailbroken Echo Show or a wall tablet for touch dashboards and confirmations.
- Cameras: 2–8 PoE cameras into Frigate.

### 5.4 Network and power
- Managed PoE switch; **IoT VLAN** for satellites and cameras, **mDNS reflector** across VLANs (ESPHome discovery breaks otherwise); Ethernet for Pi/Jetson satellites; Wi-Fi 6 AP per floor for ESP32 satellites.
- No internet exposure; **Tailscale** (or Cloudflare Tunnel behind Zero Trust) for remote access.
- UPS sized for brain + HA host + switch (Spark/Strix Halo peak ~150–250 W; a 5090 desktop ~650 W).
- Backups: HA backups nightly to NAS/cloud; Postgres/mem0/Graphiti dumps; model weights cached on NAS; satellite firmware pinned in git.

### 5.5 Bills of materials (three tiers)

| Tier | Brain | Satellites & sensors | Vision & infra | Total |
|---|---|---|---|---|
| **Budget** | Existing PC + used RTX 3090 ($700–1,050) | 2 × Voice PE ($118), 1–2 × Presence Lite ($34–76) | HA on same PC; consumer router | **≈ $900–1,400**; idle 40–80 W |
| **Prosumer (recommended)** | DGX Spark partner box ($3,699–4,699) or Strix Halo ($2,000–3,450) | 4–6 × Voice PE / 2 × Satellite1 ($450–600), 3 × presence (~$180) | N150 Frigate box ($309–339) + 2–4 PoE cams, PoE switch + UPS ($500–800) | **≈ $4,500–6,500** |
| **No-compromise** | Mac Studio M5 Ultra 512 GB (~$9–10k, uncertain) or RTX PRO 6000 build ($10–13k) or 2 × DGX Spark | Satellite1 in every room (6–8 × $135), desktop clients | Frigate on Hailo-8/TensorRT, 6–8 cams ($1,500–2,500), e-ink per floor, rack UPS, Proxmox cluster | **≈ $12,000–20,000+** |

---

## 6. Security, privacy and permissions

### 6.1 Threat model
An always-listening assistant with account access faces: (1) **indirect prompt injection** through email, calendar invites, web pages and phone notifications (demonstrated against Gemini on Android and Microsoft 365 Copilot in 2025–2026); (2) **memory poisoning** via the same channels; (3) **acoustic attacks** (someone shouting through a window, TV audio triggering the wake word); (4) **LAN compromise** (Wyoming is unauthenticated by design); (5) **cloud data exposure** (transcripts at API providers); (6) **biometric misuse** (voice/face data on household members and guests); (7) **operator error** (a model that "fabricates tool-call success", HA issue #177156).

### 6.2 Controls

| Control | Implementation |
|---|---|
| **Tiered permissions in the harness, not the prompt** | Claude Agent SDK rules (deny → ask → allow) or Pydantic AI deferred tools. **Allow:** reads, lights, media, timers, climate within bounds. **Ask (spoken or push confirmation):** locks, garage, alarm, boiler, purchases, sending messages/emails, deleting data, calendar changes affecting others. **Deny:** money movement, credential entry, anything outside allow-listed domains. Per-user overrides: children cannot unlock or buy; guests are read-only. |
| **Untrusted-content isolation** | Email bodies, web pages, calendar descriptions, notifications and camera GenAI text are labelled as data; a turn that contains fetched content cannot trigger "ask"-tier tools without confirmation regardless of what the text says; a local model pre-screens content for instruction-like patterns before it reaches the frontier model. |
| **Memory quarantine** | Facts extracted from untrusted content land in a pending queue and become memories only after the user confirms (voice or dashboard). |
| **Least privilege per MCP server** | ha-mcp read-only mode + per-tool enable + approval predicates; Playwright MCP with origin allow-lists in a disposable VM; Filesystem MCP scoped roots; separate OAuth tokens per server with minimal scopes; secrets in a vault (e.g. sops/age or Vaultwarden), never in prompts. |
| **Acoustic safeguards** | Speaker-ID gating for "ask"-tier actions (only enrolled adults can unlock); wake word disabled while media plays on that satellite unless AEC confirms; rate limits on repeated wake events. |
| **Network** | IoT VLAN; ESPHome API encryption enabled; Wyoming only on trusted VLAN; Tailscale for remote; no port forwarding. |
| **Cloud data handling** | Only transcripts and tool results leave the LAN; Anthropic API data deleted within 30 days (zero-data-retention available by agreement; Fable-tier models require 30-day retention); OpenAI ZDR for eligible API customers (Aug 2026); Google does not train on paid API data. Choose providers and models per that policy; keep a local-only mode switch. |
| **Biometrics and law** | Explicit per-person enrolment for voice and face; guest mode disables recognition, memory writes and personal tools; a visible "recording" indicator per room; hardware mute (Voice PE side switch cuts mic power; LED turns red); EDPB VVA guidelines and GDPR apply once data is shared beyond the household — obtain legal advice for your jurisdiction. |
| **Audit and rollback** | Every tool call logged with arguments, triggering content source, approver, result; ha-mcp automatic pre-edit backups; HA nightly encrypted backups (SecureTar) to NAS and off-site. |
| **Model behavior** | Prompts require tool-result verification before claiming success; strict JSON schema tool inputs; no permissions-bypass mode ever; eval red-team set with poisoned emails/pages run before every prompt or model change. |

---

## 7. Latency budget (conversational turn, prosumer tier, local speech + Claude Sonnet 5)

| Stage | Target | Notes |
|---|---|---|
| Satellite capture + network | 20–40 ms | Wi-Fi 6 on an IoT VLAN; PCM chunks of 20–32 ms |
| End-of-utterance decision | 100–250 ms after last word | Silero VAD + Smart Turn v3.2 on CPU; replaces 700–1,000 ms fixed silence |
| Streaming STT final | 80–200 ms | Nemotron/Parakeet streaming already has partials; final on EOU |
| Speaker ID + context assembly + memory recall | 50–120 ms | Parallel to STT; mem0 p50 0.88 s is too slow on the critical path → prefetch on wake and cache per session |
| Router | 20–80 ms | Heuristics first; classifier only when ambiguous |
| LLM time to first token | 300–500 ms (Sonnet 5, thinking off) / 100–200 ms (local Qwen3.6) | Prompt caching keeps stable prefix cheap and fast |
| First sentence complete | +150–300 ms | Sentence chunker sends first clause to TTS |
| TTS time to first audio | 100–200 ms (Qwen3-TTS local / Sonic 3.5) | Measured cloud TTFA 166–290 ms; local avoids network |
| Playback start | 20–40 ms | |
| **End of speech → first audio** | **≈ 600–900 ms p50** | Tier 0 intents: ≤ 300–500 ms; Tier 3 (Opus, tools): 1.5–4 s with an immediate spoken acknowledgement ("Checking your calendar…") |

Tool-calling turns: speak an acknowledgement while the tool runs; stream the answer as soon as the result lands. Never let a silent gap exceed ~1.2 s.

---

## 8. Cost model

### 8.1 One-off (prosumer tier)
Hardware ≈ $4,500–6,500 (section 5.5). Electricity at 23 W idle + ~150 W bursts ≈ 25–40 kWh/month ≈ $5–8/month at $0.18/kWh (Strix Halo/Mac lower; a 5090 desktop 2–3x higher).

### 8.2 Recurring API cost at ~200 interactions/day (6,000/month)
Assumption: two model calls per interaction, ~4k input + ~300 output tokens each (≈48M input, 3.6M output tokens/month); thinking tokens bill as output.

| Configuration | Monthly |
|---|---|
| Sonnet 5 default, 75% cache hits | ≈ $67 |
| Sonnet 5 default (80% of turns) + Opus 5 escalation (20%), cached | ≈ $90–120 |
| Add provider web search at 1 search/interaction ($10/1k) | + $60 |
| Optional S2S "conversation mode" 30 min/day on gpt-realtime-2.1-mini | + $15–45 |
| Cloud TTS (Cartesia) if used instead of local | + $5–30 depending on plan |
| **Typical total** | **$70–150/month** |
| Local-only (Tier 0/1 only) | $0 API; capex + power only |

Comparison points: GPT-5.6 Terra ≈ $139 uncached; Gemini 3.6 Flash ≈ $50; DeepSeek V4 Flash API ≈ $13 (weaker on agentic tasks and non-US data residency). Break-even of the 128 GB box versus a $100/month cloud-only bill is 2–4 years; the box is justified mainly by privacy (audio stays home), offline operation and zero marginal cost for speech.

---

## 9. Implementation roadmap

Each phase ends with a demo and an eval gate. Estimated effort assumes one experienced engineer part-time; calendar time is elastic.

### Phase 0 — Foundations (1–2 weeks)
- Order prosumer-tier hardware; set up IoT VLAN + mDNS reflector, PoE switch, UPS, Tailscale.
- Install the brain OS (DGX OS / Ubuntu), Docker, NVIDIA container toolkit; Proxmox or HA OS VM; Postgres; Langfuse; Grafana.
- Repo: monorepo with `infra/` (compose files), `pipeline/` (Pipecat app), `agent/` (harness, tools, policies), `satellites/` (ESPHome YAML), `evals/`, `docs/`.
- **Gate:** `llama-server` serving Qwen3.6-35B-A3B with tool calling; Nemotron STT and Qwen3-TTS benchmarks recorded (tok/s, TTFA, VRAM).

### Phase 1 — Voice loop on one satellite (2–3 weeks)
- Flash one Voice PE with a custom "Jarvis" microWakeWord model; HA Assist pipeline with local STT/TTS; "prefer handling commands locally"; expose ~20 entities with voice aliases.
- Pipecat service: SmallWebRTC/WebSocket ingress, Silero VAD + Smart Turn v3.2, Nemotron STT, local LLM, Qwen3-TTS, sentence chunking, barge-in.
- OpenTelemetry → Langfuse; per-stage latency dashboard.
- **Gate:** p50 ≤ 900 ms end-of-speech→first-audio on a 50-utterance script; barge-in works 9/10 while music plays; wake-word FA < 0.5/h over 48 h.

### Phase 2 — The brain and home control (3–4 weeks)
- Agent harness (Claude Agent SDK or Pydantic AI) with Claude Sonnet 5 default and Opus 5 escalation; router; prompt-caching layout; mid-conversation system messages for room/speaker context.
- HA MCP Server connected; ha-mcp-style approval predicates for locks/garage/alarm; audit log table.
- HA fronting (option 1 in 4.5): custom conversation agent forwarding non-intent turns to the brain.
- Home-control eval set (150 utterances across rooms, aliases, negations, multi-device) run nightly.
- **Gate:** ≥ 95% on the home-control eval; every "ask"-tier action produces a spoken confirmation request; cloud outage → automatic Tier 1 fallback demonstrated.

### Phase 3 — Personal agent and memory (3–4 weeks)
- Google Workspace MCP (calendar, mail, tasks), Filesystem, provider web search; Telegram/Signal MCP for outbound messages (ask-tier).
- mem0 on pgvector; Graphiti with FalkorDB/Neo4j; episodic transcript log; memory-write quarantine for untrusted content; per-user profiles.
- Speaker enrollment (ECAPA-TDNN) for household members; guest mode with read-only tools.
- Morning briefing and calendar-conflict proactive flows via HA triggers + `assist_satellite.announce`, quiet hours, rate limits.
- **Gate:** ≥ 85% on a 100-task personal-agent eval; injection red-team (poisoned email/web page) produces zero unconfirmed actions.

### Phase 4 — Whole home (2–3 weeks)
- Remaining satellites; Music Assistant + Sendspin groups; ducked announcements; room-aware routing using presence sensors; "follow me" conversation continuation in another room (start_conversation on the new room's satellite).
- Frigate on the N150 box; camera events and GenAI descriptions as tools; "who is at the door" flow.
- Desktop (linux-voice-assistant) and phone clients (HA Companion default assistant; PWA with live transcript and confirmation buttons).
- **Gate:** multi-room script (announce, timer in kitchen, question in office) passes; false wake across rooms resolves to one satellite.

### Phase 5 — Hardening and operations (2 weeks, then continuous)
- Watchdogs and health checks for every container; automatic restart; degraded-mode banners on dashboards.
- Nightly backups (HA, Postgres, memory stores); restore drill.
- Firmware pinning and staged rollout for satellites; model version pinning; eval runs before every model/prompt change.
- Security review: secrets in a vault, least-privilege tokens per MCP server, browser in a disposable VM, retention policy, hardware mute verification.
- **Gate:** chaos test (kill each service; pull internet) recovers without manual action; restore-from-backup rehearsed.

### Phase 6 — Optional upgrades
- Speech-to-speech "conversation mode" (gpt-realtime-2.1-mini / Gemini 3.1 Flash Live) behind a wake phrase.
- Phone access via SIP (HA VoIP Stack or OpenAI Realtime SIP attach).
- Vision LLM for camera Q&A (local Qwen3-VL-class or Sonnet 5 vision).
- Second brain box or Mac Studio M5 Ultra for larger open models; LiveKit SFU if many simultaneous clients appear.

---

## 10. Observability and evaluation

- **Tracing:** OpenTelemetry from Pipecat (one trace per conversation; turn → STT/LLM/TTS spans; TTFB and latency breakdown in 1.9) and from the agent harness (tool calls, permission decisions) into a self-hosted **Langfuse**; metrics into Prometheus/Grafana.
- **Dashboards:** end-to-end p50/p95, per-stage TTFB, barge-in success rate, wake-word events per hour per room (false accepts), tool success/failure by tool, tier mix and API spend, satellite health, GPU memory/temperature.
- **Alerts:** p95 end-to-end > 1,200 ms; component TTFB > 2x baseline; wake false accepts > 1/h in any room; any "ask"-tier action executed without a recorded approval; cloud provider error rate; disk/backup failures.
- **Evaluation sets (in `evals/`):** (1) 150-utterance home-control set across rooms, aliases, negations, multi-device and follow-ups; (2) 100-task personal-agent set (calendar, email, research with citations, reminders); (3) injection red-team set (poisoned emails, web pages, calendar invites, notification text) expecting zero unconfirmed actions; (4) 50-clip audio set (distances, noise, music playing) for wake word and STT WER; (5) latency benchmark script. Run nightly and before every model, prompt, or firmware change; Pipecat's YAML eval scenarios and audio playback drive the voice cases.
- **Conversation logs** stay private on the LAN; per-user retention settings; a "forget this" voice command deletes the episode and derived memories.

---

## 11. Risks, uncertainties and open questions

| Risk / uncertainty | Impact | Mitigation |
|---|---|---|
| Prices and model names for OpenAI, Google and xAI come from secondary sources (vendor sites were unreachable during research) | Cost estimates for non-Anthropic tiers may be off | Re-verify on vendor pricing pages before committing; Anthropic figures were verified directly |
| DGX Spark decode figures vary 39–61 tok/s across runtimes/benchmarks; Strix Halo prefill unverified | Model tier may feel slower than planned | Benchmark on the actual box in Phase 0 before finalizing model choices; SGLang/MTP can help |
| Mac Studio M5 Max/Ultra not yet benchmarked; 512 GB price unknown | No-compromise tier cost/perf uncertain | Wait for late-October reviews before buying |
| Voice PE has no announced successor; firmware regressions recur | Satellite supply/stability | Buy XMOS alternatives (Satellite1, XVF3800); pin firmware |
| Home Assistant 2026.9 renamed LLM tool names; continued conversation relies on punctuation heuristics | Prompt breakage; awkward follow-ups | Track release notes; implement follow-up mode in Pipecat rather than relying on HA's heuristic |
| Local models remain weaker at tool calling (37% success in tests) | Offline mode degraded | Deterministic intents cover most offline needs; escalate to cloud when available |
| Prompt injection has no complete defense ("agents may always fall for prompt injections", 2026 paper) | Real-world harm | Permissions enforced outside the model; confirmations; sandboxing; red-team evals |
| Speaker ID accuracy in far-field, multi-speaker rooms is unproven for households | Wrong user attribution | Use it for personalization, never as sole authorization for high-risk actions; combine with presence and phone confirmation |
| Smart-glasses and always-on wearables have immature developer access | Wearable Jarvis delayed | Phase 6 only; MentraOS as the open path |
| Legal exposure (GDPR/ePrivacy/AI Act) if biometric data or recordings leave the household | Compliance | Explicit enrolment, guest mode, local-first, legal advice |
| Single-engineer project mortality (the DIY norm) | Abandonment | Small, documented phases with eval gates; build on maintained frameworks and protocols |

**Open questions for the owner:** which rooms and how many satellites; which calendar/email provider; whether phone-call access is wanted; the household's stance on cameras indoors; cloud-provider preference beyond Anthropic; budget tier; jurisdiction for the legal review.

---

## 12. Appendix

### 12.1 Proposed repository layout
```
jarvis/
├── docs/                      # this plan + research notes
├── infra/                     # docker-compose / Proxmox notes, VLAN + mDNS config, backup scripts
├── satellites/                # ESPHome YAML for Voice PE / XVF3800, microWakeWord model, firmware pins
├── pipeline/                  # Pipecat app: transports, VAD/Smart Turn, STT/TTS services, barge-in, chunker
├── agent/                     # harness, router, tool registry (MCP client configs), permission policy, audit log
│   ├── prompts/               # persona, house rules, per-room defaults (versioned)
│   └── policies/              # allow/ask/deny rules per tool and per user
├── memory/                    # mem0 + Graphiti config, schemas, quarantine workflow, retention jobs
├── homeassistant/             # exposed entities, aliases, custom sentences, automations for proactive flows
├── evals/                     # home-control, personal-agent, injection red-team sets; runner; reports
└── ops/                       # dashboards (Grafana/Langfuse), alerts, runbooks
```

### 12.2 Research notes index
- [01 — DIY landscape: videos, projects, failure modes](research/01-landscape.md)
- [02 — Speech stack: STT, TTS, S2S, wake word, turn-taking, AEC, speaker ID](research/02-speech-stack.md)
- [03 — Brain: LLMs, inference servers, agent frameworks, MCP, memory, safety, cost](research/03-llm-agents-memory.md)
- [04 — Hardware: servers, satellites, sensors, networking, tiers](research/04-hardware.md)
- [05 — Orchestration frameworks, Home Assistant, integrations, multi-room, observability](research/05-orchestration-home-assistant.md)
- [06 — UX, vision, proactive behavior, privacy, operations, market context](research/06-ux-vision-privacy-ops.md)

### 12.3 Glossary
AEC acoustic echo cancellation · ASR/STT speech-to-text · EOU end of utterance · HA Home Assistant · MCP Model Context Protocol · MoE mixture of experts · NS noise suppression · S2S speech-to-speech · TTFA/TTFB time to first audio/byte · TTS text-to-speech · VAD voice activity detection · Wyoming/ESPHome the satellite protocols used by Home Assistant.
