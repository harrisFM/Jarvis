# Research Note 05 — Orchestration frameworks, Home Assistant as hub, integrations, multi-room, observability

Research date: 2026-09-11. Home Assistant facts come mostly from the raw markdown of the `home-assistant/home-assistant.io` and `developers.home-assistant` repos (2026.1–2026.9 release posts); framework facts from GitHub repos/changelogs and search summaries. Items not verifiable from a primary source are marked **(uncertain)**.

## 1. Voice-agent orchestration frameworks

### Open-source, self-hostable

**Pipecat (Daily)** — Python, BSD-2-Clause, ~15.4k stars. Frame-pipeline model; **v1.0.0 on 14 April 2026**; 1.8.0 (2026-08-26: MCP tools via `MCPClient.tools()`, "proposed turn frames", MoQ client), 1.8.1, **1.9.0 (2026-09-10**, latency-breakdown metrics). 2026 also added a multi-agent bus, Pipecat Flows, TTFA metrics, SIP DTMF, a **PocketTTS CPU-only local TTS service** and local Whisper STT variants. Integrations: 20+ STT, 25+ LLMs (Anthropic, OpenAI, Gemini, **Ollama**…), 30+ TTS (Cartesia, ElevenLabs, **Kokoro**…); transports: Daily WebRTC, **SmallWebRTCTransport (P2P, no cloud)**, FastAPI/WebSocket, LiveKit, WhatsApp; telephony serializers for Twilio, Telnyx, Plivo, Vonage. **Turn detection: Smart Turn v3.2** — open (BSD-2) audio-native end-of-turn model, ~8M params, 8 MB int8 CPU build, 10–100 ms, 23 languages, weights + training data + scripts published; runs fully local via ONNX. Ships OpenTelemetry tracing with per-turn STT/LLM/TTS spans.

**LiveKit Agents** — Python (Node via AgentsJS), Apache-2.0, ~14.1k stars. Runs on the Apache-2.0 LiveKit media server (WebRTC SFU, self-hostable; v1.13.6 Aug 2026). **1.5 (April 2026)** added an audio-based interruption model and native MCP tools; 1.6–1.8.1 added a unified audio end-of-turn `TurnDetector`, adaptive interruption for realtime models, PII redaction, **OpenTelemetry GenAI semantic conventions (1.8.0)**, Deepgram Flux, and a `DuplexModel` class. Caveat: the full v1 turn-detection model runs only on LiveKit Cloud; self-deployed agents run **v1-mini** locally (<500 MB RAM, CPU). Model weights are under a "LiveKit Model License", not Apache.

**TEN Framework (Agora)** — ~11.1k stars; Apache-2.0 "with additional restrictions". Extension-graph architecture; TEN VAD + TEN Turn Detection (full-duplex); **ESP32-S3 Korvo** reference; Docker deployment. 0.11.71 (31 July 2026) added a Claude extension. Pre-1.0 and Agora-RTC-centric.

**Vocode** — last commit November 2024; dormant. **Ultravox (Fixie)** — MIT, v0.7 (Dec 2025): audio encoder + adapter onto Llama 3.3; **emits streaming text, not speech**; hosted $0.05/min.

### Hosted speech-to-speech / provider APIs

**OpenAI Realtime API + Agents SDK** — `gpt-realtime-2.1` and `-2.1-mini` (6 July 2026) with configurable reasoning and tool use; p95 latency down ≥25%. Pricing (secondary): $32/1M audio-in, $64/1M out; mini $10/$20 — ≈$0.05/min base, ≈$0.016/min mini. Agents SDK `RealtimeAgent`/`RealtimeRunner`, **SIP attach via the Realtime Calls API**, semantic-VAD turn detection with `interrupt_response`, `RealtimePlaybackTracker`, tool-approval hooks. The older cascaded `VoicePipeline` has no built-in interruption handling.

**Google Gemini Live API / ADK** — bidi-streaming 16 kHz in / 24 kHz out, barge-in, **proactive audio**, **affective dialog**, function calling + Google Search, 70 languages. Exact 2026 pricing not verified **(uncertain)**.

**ElevenLabs Agents** — STT+LLM+TTS with proprietary turn-taking model; ~$0.10/min falling to ~$0.08 on Business. Hosted only. **Deepgram Voice Agent API** — unified STT+LLM+TTS at **$4.50/hr (~$0.075/min)**; Flux integrated end-of-turn. **Speechmatics Flow** — $0.0537/min. **Hume EVI** — emotion-aware S2S, overage $0.06→$0.04/min.

### Call-center platforms (poor fit)
**Vapi** (~$0.05/min platform fee + providers; 500–1,500 ms), **Retell** (~$0.07/min), **Bland** — hosted, phone-first, per-minute pricing: poor economics for a mic that listens all day. **Layercode**, **Vogent** — hosted; details partially unverified.

### Comparison

| Framework | Model | License / self-host | Turn detection & interruption | Telephony / WebRTC | Local STT/TTS/LLM | Fit for always-on home Jarvis |
|---|---|---|---|---|---|---|
| Pipecat 1.9 | Cascaded or S2S | BSD-2, fully self-host | Smart Turn v3.2 (open, 10–100 ms CPU), VAD, turn frames | Twilio/Telnyx/Plivo, SIP DTMF, SmallWebRTC | Whisper, PocketTTS, Kokoro, Ollama | **Best** |
| LiveKit Agents 1.8 | Cascaded or S2S/Duplex | Apache-2.0 (weights: LiveKit license) | Audio EOT TurnDetector (v1-mini self-hosted), audio interruption model | Native SIP, WebRTC SFU | Ollama, local Whisper plugins | **Very good**, heavier infra |
| TEN 0.11 | Cascaded/S2S | Apache-2.0 + restrictions | TEN VAD + Turn Detection | Agora RTC, WebSocket | Partial | Good ESP32 reference; less mature |
| OpenAI Realtime + Agents SDK | S2S | Hosted | Semantic VAD | SIP attach | No | Good "chatty" tier |
| Gemini Live + ADK | S2S | Hosted | Native VAD, barge-in, proactive audio | Partner telephony | No | Good alternative |
| ElevenLabs Agents | Cascaded (hosted) | Hosted | Proprietary | Twilio/SIP, WebRTC | No | Great voices; hosted only |
| Deepgram Voice Agent | Cascaded (hosted) | Hosted | Flux EOT | WebSocket | No | Cheap unified stack |
| Vapi / Retell / Bland | Hosted | Hosted | Vendor | Phone-first | No | Call-center; poor fit |
| Vocode | Cascaded | MIT, dormant | Basic | Twilio | Some | Avoid |

## 2. Home Assistant as the hub (2026)

**Architecture.** The Assist pipeline runs wake word → STT → intent recognition (conversation agent) → TTS over a WebSocket API with binary audio chunks, VAD, an audio enhancer and ring buffer. Remote services attach via **Wyoming**, a peer-to-peer JSONL+PCM TCP protocol (audio, wake, ASR incl. streaming `transcript-chunk`, TTS streaming `synthesize-chunk`, intent, satellite control); it has **no auth or encryption** — trusted LANs only. Satellites expose an `assist_satellite` entity (idle/listening/processing/responding) with `announce` and `start_conversation` features; 2026.2 added satellite-state conditions.

**Local speech stack.** Speech-to-Phrase (OHF-Voice, Apache-2.0): Kaldi FST from sentence templates + entity/area names — "under one second" on a Pi 4 but only a subset of commands. Whisper via wyoming-faster-whisper is open-ended but ~8 s on a Pi 4, <1 s on a NUC. Piper (`piper1-gpl`, GPL-3.0, OHF seeking maintainers). Wake words: openWakeWord, microWakeWord. Home Assistant Cloud is testing **Soniox** STT in 2026.9 Labs.

**LLM conversation agents.** Built-in: OpenAI (GPT-5.6 in 2026.8; web search), Anthropic (Opus 4.7 in 2026.5; web search, **web fetch (2026.6)**, code execution, prompt caching, thinking shown in UI since 2026.4), Google Gemini (search grounding; TTS/STT entities), Ollama (default 8k context; advice to expose **<25 entities**, possibly two instances for chat vs control), plus **LiteLLM** and **llama.cpp/OpenAI-compatible** agents in 2026.8. Each agent has **"Control Home Assistant"** and **"Prefer handling commands locally"** (HA answers what it can; LLM only otherwise). Since Voice Chapter 10 (June 2025) an LLM question keeps the mic open (**continued conversation**) and automations can `start_conversation`. **Backward-incompatible in 2026.9:** LLM tool names are domain-prefixed (`intent__HassTurnOn`, `homeassistant__GetLiveContext`).

**MCP both directions.** **MCP Server** integration exposes the Assist API at `/api/mcp` (Streamable HTTP/SSE, OAuth or long-lived token; Tools, Prompts, read-only Resources; no Sampling/Notifications). **MCP client** integration lets HA agents consume external MCP servers (SSE only; mcp-proxy for stdio). Community `mcp-assist` replaces the full entity dump ("12,000+ tokens" for 200+ devices) with on-demand discovery (~400 tokens).

**Other 2026 changes.** 2026.3: experimental **on-device wake word on Android** (microWakeWord; only the fastest nearby satellite answers). 2026.5: timer lifecycle triggers and media-player conditions for volume-aware TTS. 2026.7: natural-language triggers/conditions and area-based targets. Voice PE firmware 25.12.2 added **Sendspin** multi-room audio; 26.x releases focused on Sendspin sync and letting HA request unprocessed audio for specialised STT. `wyoming-satellite` archived 27 Jan 2026 → **linux-voice-assistant** (ESPHome protocol; wake-word interruption, continued conversation, timers, announcements).

**Known limitations.** No native speaker identification (community add-on only); Wyoming unauthenticated; LLM latency on Pi-class hardware poor; 2026 release notes contain **no** new multi-room conversation handoff or speaker-ID pipeline features.

## 3. Alternatives and complements
- **openHAB 5.1.4**: community-only local voice add-ons; no Assist equivalent. **Hubitat**: Ollama experiments only. **Node-RED**: fine as an automation layer beside HA.
- **Rhasspy 3**: archived 6 Oct 2025. **OVOS/Neon**: ovos-core 3.5.x alphas Sept 2026; niche. **Willow**: alive but episodic, ESP32-S3-BOX centric.
- **Frigate** 0.17.x (0.18 RC in Sept 2026): GenAI review summaries with local llama.cpp provider, semantic search, face and plate recognition — a natural "eyes" input via MQTT/HA.
- **Matter/Thread**: HA Matter Server rebuilt on **matter.js** (June 2026) with **Matter 1.5.1**; users still report devices going unavailable after updates.

## 4. Personal-life integrations (MCP ecosystem, 2026)
- **Google**: official managed Workspace MCP servers (Gmail, Calendar, Docs, Sheets, Slides) rolling out from 1 May 2026; community `taylorwilsdon/google_workspace_mcp` (MIT, 3.1k stars, 120+ tools).
- **Microsoft 365**: "Work IQ Calendar (Preview)" official MCP; community `Softeria/ms-365-mcp-server` (300+ tools).
- **Messaging**: `lharries/whatsapp-mcp` (6.3k stars; unofficial API — ban risk; README warns of prompt-injection exfiltration); Telegram MCP; Signal MCP over signal-cli; iMessage-database MCP (macOS).
- **Music**: Music Assistant **2.10.2 (4 Sep 2026)**, 2.11 beta (Sendspin pairing); MA's Sonos/Snapcast/Sendspin players support **native announcements** with pre-announce chime and volume ducking. `spotify-mcp` marked inactive. Snapcast 0.35.0 (Mar 2026).
- **Web search**: Brave $5/1k; Exa $7/1k; Tavily ~$8/$16 per 1k; Perplexity Sonar $0.20–$15/M tokens. HA's Anthropic/OpenAI/Gemini agents expose provider-side web search (zero plumbing).
- **Telephony**: HA `voip` integration via Grandstream HT801/802; community **VoIP Stack 2026.9.0** (SIP registrar in HA/ESPHome); Twilio add-on to phone Assist; OpenAI Realtime SIP attach.

## 5. Multi-room, multi-user design
HA resolves "the lights" against the **satellite's area**; announcements/`start_conversation` target satellites or MA players; when several satellites hear the wake word only the fastest answers; whole-home sync audio via Sendspin (Voice PE, MA), Snapcast, Sonos or Cast; speaker ID is add-on-only. No native room-to-room handoff of an in-progress conversation found **(uncertain — absence of evidence)**. Practical pattern: one brain process per household, one satellite per room, room identity carried as metadata into the LLM context, MA/Sendspin as the output bus.

## 6. Remote access and mobile
Android Companion can be the **default assistant app** and (≥2026.2.3) run local microWakeWord; iOS exposes App Intents/Siri Shortcuts (known issue #108503: Siri "Assist" shortcut always hits the default agent). Remote access: Tailscale add-on, Cloudflared add-on (Zero Trust), or Nabu Casa cloud. Proactive behaviour is native in HA (time/state/timer triggers → `assist_satellite.announce` or `start_conversation`, `ai_task.generate_data` for briefings).

## 7. Observability and evaluation
Pipecat and LiveKit both emit OpenTelemetry: Pipecat one trace per conversation with turn → STT/LLM/TTS spans, TTFB and (1.9.0) latency-breakdown metrics; LiveKit 1.8 adopted OTel GenAI semantic conventions with PII redaction, natively ingested by Langfuse and Datadog. Guides recommend alerting at p95 > 800 ms (warn) / > 1,200 ms (critical) end-to-end. Pipecat 1.x's built-in **evals** (YAML scenarios, audio playback) and LiveKit's testing framework plus a local Langfuse keep transcripts private. HA shows per-turn tool calls/reasoning in the Assist dialog (2026.4).

## Recommendations
1. **Keep Home Assistant as the device/intent hub, not the conversational brain.** Use it for entity exposure, area resolution, timers, announcements, sentence triggers and "prefer handling commands locally" fast-path intents. Expose its Assist API to the brain via the MCP Server integration; keep exposed entities lean or use mcp-assist-style discovery.
2. **Build the brain on Pipecat** (BSD-2, self-hostable, Smart Turn on CPU, first-class MCP client, local Whisper/PocketTTS/Kokoro/Ollama, OTel built in, SmallWebRTC so no cloud account is required). Choose LiveKit Agents if you want a WebRTC SFU for many simultaneous clients or native SIP.
3. **Tier the LLM.** Local model for control and short talk; `gpt-realtime-2.1-mini` or Gemini Live as optional S2S tier; frontier text models through MCP tools for email/calendar. Avoid Vapi/Retell/Bland/ElevenLabs Agents as the core.
4. **Rooms and audio:** Voice PE or linux-voice-assistant per room; Music Assistant + Sendspin/Snapcast for synchronized output and ducked announcements; add speaker-recognition add-on if per-user context matters; tag every turn with room and speaker.
5. **Remote:** Tailscale (or Cloudflare Tunnel behind Zero Trust); Twilio/OpenAI SIP attach if you want to *call* Jarvis.
6. **Instrument from day one:** OTel → self-hosted Langfuse; track TTFB per stage, end-to-end p95, barge-in outcomes; version prompts and run eval scenarios before changing models. Watch the 2026.9 tool-name prefix change.

## Sources
- https://github.com/pipecat-ai/pipecat · https://raw.githubusercontent.com/pipecat-ai/pipecat/main/CHANGELOG.md · https://github.com/pipecat-ai/smart-turn · https://www.daily.co/blog/announcing-smart-turn-v3-with-cpu-inference-in-just-12ms/
- https://github.com/livekit/agents · https://github.com/livekit/agents/releases · https://github.com/livekit/agents/tree/main/livekit-plugins/livekit-plugins-turn-detector · https://github.com/livekit/livekit/releases
- https://github.com/TEN-framework/ten-framework · https://github.com/vocodedev/vocode-core · https://github.com/fixie-ai/ultravox
- https://mer.vin/2026/07/gpt-realtime-2-1-api-reasoning-voice-agents-and-mini-pricing/ · https://github.com/openai/openai-agents-python/blob/main/docs/realtime/guide.md · https://github.com/google-gemini/gemini-live-api-examples
- https://pxlpeak.com/blog/ai-tools/elevenlabs-pricing-guide · https://diyai.io/ai-tools/speech-to-text/deepgram-pricing-2026/ · https://www.speechmatics.com/pricing · https://medium.com/@automation.labs/vapi-vs-retell-vs-bland-in-2026-the-true-cost-per-minute-578f38af3523
- Home Assistant raw docs: https://raw.githubusercontent.com/home-assistant/home-assistant.io/current/source/_posts/2026-0{1..9}-*-release-2026{1..9}.markdown · …/2025-06-25-voice-chapter-10.markdown · …/2026-06-23-the-matter-upgrade-youve-been-waiting-for.markdown · …/source/_integrations/{mcp_server,mcp,ollama,anthropic,openai_conversation,google_generative_ai_conversation,voip}.markdown · …/source/voice_control/voice_remote_local_assistant.markdown · https://raw.githubusercontent.com/home-assistant/developers.home-assistant/master/docs/voice/pipelines/index.md · …/docs/core/entity/assist-satellite.md
- https://github.com/OHF-Voice/wyoming · https://github.com/OHF-Voice/speech-to-phrase · https://github.com/OHF-Voice/linux-voice-assistant · https://github.com/OHF-Voice/piper1-gpl · https://github.com/esphome/home-assistant-voice-pe/releases · https://github.com/home-assistant/android/releases · https://github.com/mike-nott/mcp-assist · https://github.com/EuleMitKeule/speaker-recognition
- https://github.com/HeyWillow/willow · https://github.com/OpenVoiceOS/ovos-core/releases · https://github.com/blakeblackshear/frigate/releases · https://community.home-assistant.io/t/matter-thread-devices-unavailable/971940
- https://github.com/music-assistant/server/releases · https://github.com/Sendspin · https://github.com/badaix/snapcast/releases · https://www.music-assistant.io/integration/announcements/
- https://github.com/taylorwilsdon/google_workspace_mcp · https://workspaceupdates.googleblog.com/2026/05/agent-tools-and-security-updates-for-workspace-developers.html · https://github.com/Softeria/ms-365-mcp-server · https://github.com/lharries/whatsapp-mcp
- https://fastcrw.com/blog/web-search-api-pricing-2026 · https://community.home-assistant.io/t/voip-stack-for-home-assistant-and-esphome/1016178 · https://github.com/hassio-addons/addon-tailscale · https://github.com/brenner-tobias/addon-cloudflared · https://github.com/home-assistant/core/issues/108503
- https://langfuse.com/integrations/frameworks/pipecat · https://langfuse.com/integrations/frameworks/livekit · https://docs.pipecat.ai/server/utilities/opentelemetry · https://hamming.ai/resources/opentelemetry-voice-agents-tracing-guide
