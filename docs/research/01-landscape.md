# Research Note 01 — The "Build Your Own Jarvis" landscape, 2024–2026

Research date: 2026-09-11. GitHub data (stars, last push, READMEs, issues) was pulled directly from GitHub. YouTube titles/IDs/dates come from search-engine snippets (reliable); channel names, view counts and comment criticism could not be verified for most videos and are marked uncertain.

## 1. YouTube videos and creators

The genre splits into three generations that coexist today.

**(a) Classic Python scripts (2020–2024, still being uploaded).** `speech_recognition` (Google web STT), `pyttsx3` TTS, `wikipedia`, `pywhatkit`, `pyautogui`; no LLM. Canonical: freeCodeCamp "How to Build Tony Stark's JARVIS with Python", GauravSingh9356/J.A.R.V.I.S (1.4k stars, MIT, no LLM), Udemy "Learn to Build AI assistant like JARVIS using Python", PyPI `JarvisAI` (v4.4). Videos: "Voice AI Assistant using Python Tutorial | Build JARVIS with Google Gemini" (watch?v=9SWZ_2orbfI, 25 July 2024), "Build Your Own JARVIS AI Assistant – Complete Python Tutorial" (VuZBVFuImpY, 23 April 2026) — both swap the rule-based brain for the Gemini API but keep the blocking record→transcribe→speak loop.

**(b) Home-Assistant / local-LLM builds (2024–2026).** NetworkChuck's multi-part series on replacing Alexa with a fully local voice assistant (youtu.be/XvbVePuP7NY; Home Assistant + Rhasspy/Wyoming satellites + Whisper + Piper + Ollama; part 3 cloned a celebrity voice locally). "Home Assistant Voice + Ollama = Snarky AI?!" (5mjK821ETPA) and TechteamGB's "Home Assistant Voice & Ollama Setup Guide" (28 Feb 2025) show the $59 Voice Preview Edition driving an Ollama conversation agent. Criticisms from reviews (Geeky-Gadgets, Matter Alpha, Botmonster): local LLM averaged **3.89 s** response with only **37% task success**, cloud LLM **58%** success at **5.21 s**; wake-word accuracy drops in noisy rooms; interrupting a response requires saying the wake word twice; entities must be renamed conversationally and manually exposed.

**(c) Cloud speech-to-speech / agent builds (late 2025–2026).** Riley Brown (X: @rileybrown; "How to Create Your Own AI Assistant (It's So Easy)", 4WBOmhI11rQ) built "RileyJarvis": a local Electron app using **GPT-Realtime-2** with tools for Exa web search, local notes, Mermaid diagrams, image generation and macOS computer control, vibe-coded "in under 20 minutes" (mid-2026, uncertain). "I Built JARVIS With OpenAI's New Voice AI" (aYbSO1Q7lHw). "How I Built JARVIS AI Voice Agent with Claude Code + Livekit (100% Free!)" (8FEo2RqOSCI, 23 April 2026) and "I Built JARVIS with Claude Code (INSANE Results!)" (Acw0NtkyNtM) use LiveKit Agents or a `claude -p` process as the brain. "Jarvis Mark 53 – Step by Step Guide" (K_cha25S4Qo, ~9 Sept 2026). aifire.co: "Build Your Own Jarvis AI Assistant in 3 Prompts (No Code)" (Codex + GPT-Realtime-2).

Common criticism across all generations (from READMEs/issue trackers): demos hide first-response latency, wake-word misfires, and the fact that the "assistant" only works on the creator's laptop with API keys.

## 2. Open-source projects (stars and activity as of 2026-09-11)

| Project | Stars | Last push | Status / architecture | Strengths | Weaknesses |
|---|---|---|---|---|---|
| **OpenClaw** (openclaw/openclaw) | 389k | 2026-09-11 | Local gateway + messaging channels (WhatsApp/Telegram/Slack/Discord/iMessage) + skills; companion apps add voice; created Nov 2025 | Enormous ecosystem (awesome-openclaw-skills 52k stars, 5,400+ skills incl. "Jarvis Voice") | Chat-first; README warns inbound messages are untrusted; tools run unsandboxed on host |
| **LocalAI** (mudler) | 49k | 2026-09-11 | Go OpenAI-compatible server: LLM, STT, TTS, MCP | One-binary backend | Infrastructure, not an assistant |
| **Leon** (leon-ai) | 17.5k | 2026-09-11 | Node ≥24 + Python; 2.0 Developer Preview: smart/controlled/agent modes, layered memory, computer use | Longest-running (2019), active | Docs "not ready yet"; last tagged releases Feb 2025 pre-releases |
| **Pipecat** (pipecat-ai) | 15.4k | 2026-09-11 | Frame/pipeline framework, 25+ STT, 30+ LLM, 40+ TTS, S2S; v1.0.0 April 2026 | Vendor-agnostic, local transport | Not turnkey |
| **LiveKit Agents** | 14.1k | 2026-09-11 | AgentSession, transformer turn-detector, native MCP, realtime models, self-hostable WebRTC | Production interruption handling (v1.5.6: 86% precision / 100% recall) | Complexity |
| **Moshi** (kyutai-labs) | 11k | 2026-09-09 | Full-duplex speech-text model, Mimi codec; ~200 ms on L4; 24 GB VRAM, 4-bit MLX on M3 | True duplex, on-device on Mac | No tool use; weak reasoning |
| **GLaDOS** (dnhkng) | 5.7k | 2026-08-09 | Silero VAD → Parakeet TDT (ONNX) → OpenAI-compatible LLM → Kokoro TTS; FastVLM vision; MCP tools; "Society of Mind" subagents; <600 ms target; runs on 8 GB Rock5b | Best-engineered hobby build | Streaming ASR WIP; ROCm unsupported (#209); memory tool-calling reliability (#218) |
| **Piper1-gpl** (OHF-Voice) | 5.5k | – | Open Home Foundation successor to rhasspy/piper | Default local TTS | "Seeking maintainers" |
| **01** (openinterpreter) | 5.2k | **2024-11-01** | LMC-message server, ESP32/desktop/mobile clients | Early voice-first computer control | Dormant; hardware cancelled; "lacks basic safeguards" |
| **RealtimeVoiceChat** (KoljaB) | 3.8k | 2025-07-11 | RealtimeSTT → Ollama → Kokoro/Coqui/Orpheus | Reference low-latency local loop | Author stepped back; needs CUDA |
| **Willow** (HeyWillow) | 3.1k | 2026-09-01 | ESP-IDF on ESP32-S3-BOX; Willow Inference Server; <500 ms claims | Best embedded wake-word latency | Last release 0.4.3 on 21 July 2024; no LLM story |
| **openWakeWord** (dscripka) | 2.8k | 2025-12-30 | ONNX models incl. "hey_jarvis"; <5% false-reject, <0.5 false-accept/hour targets | De-facto DIY wake word | English-only, noise sensitivity |
| **isair/jarvis** | 1.7k | 2026-08-25 | Whisper (hallucination filter) → ~2B "intent judge" + big chat model via Ollama → Piper/Chatterbox; knowledge-graph memory; embedding-based MCP tool selection | Most complete "Jarvis-named" project | Voice-only; #24 "stop" commands filtered as echo; #147 Whisper hallucination |
| **Unmute** (kyutai-labs) | 1.5k | – | Kyutai STT/TTS wrapping any LLM via vLLM; ~450–750 ms | Local cascade with SOTA speech | x86_64 + ≥16 GB VRAM only |
| **Dicio** (DicioTeam) | 1.5k | 2026-07-25 | Kotlin Android, Vosk STT, skills; F-Droid | Real phone assistant | No LLM |
| **ethanplusai/jarvis** | 740 | 2026-09-10 | Chrome Web Speech STT → persistent `claude -p` → Fish Audio TTS; FastAPI + Three.js; MCP | Runs on Claude subscription | macOS+Chrome only; no wake word |
| **OHF-Voice/linux-voice-assistant** | 614 | 2026-09-03 | ESPHome-protocol satellite, openWakeWord/microWakeWord, wake-word interruption, continued conversation | Official successor to wyoming-satellite | Needs 1 GHz/512 MB Linux |
| **OVOS ovos-core** | 287 | 2026-09-10 | Mycroft successor; plugin STT/TTS/wake word, ovos-persona for LLMs; stable 2.1.1 (Nov 2025); NLnet-funded | Only full assistant OS with skills, RPi images | Small core community |
| **rhasspy3 / wyoming-satellite** | 382 / – | archived | wyoming-satellite archived **27 Jan 2026** ("replaced by Linux Voice Assistant") | Wyoming protocol lives on (wyoming-faster-whisper Aug 2026) | Rhasspy as a product is over |
| Long tail | | | llm-guy/jarvis (331), AlexandreSajus/JARVIS (527, dead since Jun 2024), RoyalCities/RC-Home-Assistant-Low-VRAM (247), InterGenJLU/jarvis (Qwen3.5-35B-A3B on RX 7900 XT, "2–4 s first spoken word"), ndunl075/Jarvis ("15–45 s first reply on CPU") | | |

## 3. Shared patterns and failure modes

1. **Latency.** 1–2 s on an RTX 3060 with Llama-3.1-8B + Whisper-small; 5–8 s on a Raspberry Pi 5; 15–45 s CPU first reply. GLaDOS's author calls 600 ms the threshold below which conversation stops feeling stilted; production budgets cite <800 ms as "natural". Most tutorials are non-streaming, so latency = STT + full LLM generation + TTS.
2. **Wake word false accepts/rejects.** microWakeWord's README admits "training a model that works well is still very difficult". Home Assistant Voice PE suffered repeated regressions: core #157932 "[2024.12] microWakeWord broken", #165860 (2026.3.2), #167989 (ESPHome 2026.3.x PSRAM fragmentation), #167259 (2026.4.0 breaks Speech-to-Phrase).
3. **Echo / self-hearing and barge-in.** Without AEC the assistant transcribes its own TTS. isair/jarvis filters echo and then loses "stop" commands (#24); Voice PE needs the wake word twice to interrupt. Only LiveKit/Pipecat (semantic turn detection) and duplex models handle this properly.
4. **STT hallucination.** Whisper invents text on silence/noise (isair #147; Willow #340).
5. **Brittle tool calling.** HA issues: #167154 Ollama qwen3 puts tool calls inside thinking content; #176324 aliases break HassTurnOn; #177156 Anthropic agent "fabricates tool-call success"; #177965/#178033 intents report success on unavailable entities; #169315 "prefer handling commands locally" bypassed. Smaller local models fail more (37% success).
6. **No memory / personalization.** 2026 builds bolt on SQLite+FAISS, knowledge graphs, or Markdown files. GLaDOS #218 asks which local LLM is reliable enough for memory tool calls.
7. **Cloud dependency disguised as "Jarvis".** Many impressive builds are keyed to paid APIs and one OS.
8. **Single user, single device, single room.** No project surveyed does speaker identification (GLaDOS #182 open request); multi-room exists only via Home Assistant satellites.
9. **Project mortality.** June, AlexandreSajus/JARVIS, 01, RealtimeVoiceChat, Willow (releases), rhasspy3, wyoming-satellite are dormant or archived; the "template repo" half-life is roughly one year.

## 4. 2023-style vs 2026 state of the art

| Dimension | 2023 Python script | 2026 SOTA DIY |
|---|---|---|
| Loop | Blocking record → Google STT → if/else or GPT-3.5 → pyttsx3 | Always-on VAD (Silero) + wake word → streaming ASR (Parakeet, Kyutai STT) → streaming LLM sentence-chunked into streaming TTS (Kokoro, Pocket TTS) |
| Brain | Rule table or single chat completion | Two-tier: small "intent judge" + larger chat model, or MoE like Qwen3.5-35B-A3B; native tool calling |
| Tools | Hard-coded `webbrowser.open` | MCP servers with embedding-based tool selection; Home Assistant as MCP server/client |
| Turn-taking | None | Transformer turn detectors (LiveKit), Smart Turn (Pipecat), full-duplex S2S |
| Speech-to-speech | – | gpt-realtime-2 / Gemini Live (cloud); Moshi, Unmute (local) |
| Memory | None | Knowledge graph / vector store / Markdown; "digest passes" |
| Hardware | Laptop mic | ESP32-S3 satellites, Linux satellites via ESPHome protocol, GPU inference boxes |
| Distribution | Copy-paste script | Docker compose, single binaries, PyPI |
| Ecosystem | Standalone | OpenClaw skills, Home Assistant Assist pipelines, Claude Code sessions |

Practical 2026 recommendation implied by the evidence: use LiveKit Agents or Pipecat (or GLaDOS as a reference) for the audio pipeline, a two-model LLM setup with MCP tools, openWakeWord/microWakeWord satellites, and accept that reliable barge-in and multi-user support are still frontier problems even for well-funded projects.

## Sources
- https://github.com/openclaw/openclaw · https://github.com/VoltAgent/awesome-openclaw-skills
- https://github.com/mudler/LocalAI · https://github.com/leon-ai/leon
- https://github.com/pipecat-ai/pipecat · https://github.com/livekit/agents
- https://github.com/kyutai-labs/moshi · https://github.com/kyutai-labs/unmute
- https://github.com/dnhkng/GLaDOS · https://github.com/openinterpreter/01 · https://github.com/HeyWillow/willow
- https://github.com/isair/jarvis · https://github.com/ethanplusai/jarvis · https://github.com/Julian-Ivanov/jarvis-voice-assistant
- https://github.com/dscripka/openWakeWord · https://github.com/kahrendt/microWakeWord · https://github.com/hexgrad/kokoro · https://github.com/OHF-Voice/piper1-gpl · https://github.com/OHF-Voice/linux-voice-assistant
- https://github.com/rhasspy/rhasspy3 · https://github.com/rhasspy/wyoming-satellite · https://community.rhasspy.org/t/2026-the-real-future-of-rhasspy-the-end/5872
- https://github.com/OpenVoiceOS/ovos-core · https://github.com/DicioTeam/dicio-android · https://github.com/mezbaul-h/june · https://github.com/KoljaB/RealtimeVoiceChat
- Home Assistant issues: core #165860, #167989, #167259, #157932, #167154, #176324, #177156, #177965, #178033, #169315
- https://www.home-assistant.io/voice-pe/ · https://www.home-assistant.io/blog/2025/09/11/ai-in-home-assistant/ · https://www.home-assistant.io/blog/2025/10/22/voice-chapter-11/
- https://www.geeky-gadgets.com/home-assistant-voice/ · https://www.matteralpha.com/review/home-assistant-voice-preview-edition-review · https://techteamgb.co.uk/2025/02/28/home-assistance-voice-ollama-setup-guide-the-ultimate-local-llm-solution/
- YouTube: watch?v=9SWZ_2orbfI · VuZBVFuImpY · K_cha25S4Qo · aYbSO1Q7lHw · 5mjK821ETPA · 8FEo2RqOSCI · Acw0NtkyNtM · 4WBOmhI11rQ · youtu.be/XvbVePuP7NY
- https://x.com/rileybrown/status/2072127866507014600 · https://www.aifire.co/p/build-your-own-jarvis-ai-assistant-in-3-prompts-no-code
- https://www.freecodecamp.org/news/python-project-how-to-build-your-own-jarvis-using-python/
- https://dev.to/remi_etien/i-built-a-voice-ai-with-sub-500ms-latency-heres-the-echo-cancellation-problem-nobody-talks-about-14la
- https://softcery.com/lab/ai-voice-agents-real-time-vs-turn-based-tts-stt-architecture · https://www.ultravox.ai/blog/introducing-the-ultravox-integration-for-pipecat
