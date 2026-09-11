# Research Note 02 — The speech layer (STT, TTS, S2S, wake word, turn-taking, AEC, speaker ID)

Research date: 2026-09-11. ~50 searches and ~25 page fetches. Several vendor domains were unreachable from the research environment, so some vendor numbers come from search snippets or third-party benchmark sites; those are marked **(uncertain)**. Vendor latency claims are almost always "model inference only"; independent measurements add 100–300 ms for network/TLS.

## 1. Streaming speech-to-text (ASR)

**What changed in 2025–26.** The field split into (a) streaming-native architectures (Kyutai DSM, Voxtral Realtime, NVIDIA cache-aware Nemotron, Moonshine v2, GPT-Realtime-Whisper, Scribe v2 Realtime) and (b) chunked wrappers around offline Whisper. For a conversational assistant the first class is now clearly better: sub-300 ms partials, built-in VAD/turn signals, no 30-second-window hacks.

**Cloud.** ElevenLabs Scribe v2 Realtime (Nov 2025): ~150 ms latency across 90+ languages, claims lowest FLEURS WER of any low-latency ASR. AssemblyAI Universal-3 Pro Streaming (sub-300 ms, real-time diarization, 6-language code-switching) and Universal-3.5 Pro Realtime at 534 ms p95. Deepgram Nova-3 is the latency leader (<300 ms time-to-final) but independent Coval tests placed it near the bottom on accuracy on their hard set (25% WER vs 4.2% for AssemblyAI) — dataset-dependent. Deepgram Flux fuses end-of-turn detection into ASR (median EOT <300 ms; $0.0065/min English, $0.0078/min 10-language). OpenAI GPT-Realtime-Whisper (7 May 2026) is a streaming STT model in the Realtime API. Mistral Voxtral Realtime (Feb 2026) is open-weights (Apache-2.0) 4B streaming with latency configurable to sub-200 ms. Speechmatics Ursa 2 (55 languages, 500 ms partials). Google Chirp 3 streaming $0.016/min.

**Local.** NVIDIA Nemotron-3.5-ASR-Streaming-0.6B (June 2026, Apache-2.0, 40 languages, cache-aware, chunk sizes 80 ms–1.12 s) and Parakeet-unified-en-0.6b (April 2026, English, offline+streaming, 160 ms minimum latency). Parakeet-tdt-0.6b-v3 / Canary-1b-v2 (Aug 2025, 25 European languages) are the offline workhorses. Kyutai STT (CC-BY-4.0): 1B EN/FR with 0.5 s delay and semantic VAD; 2.6B EN with 2.5 s delay; the 1B runs on an iPhone 16 Pro via MLX. Moonshine v2 (Feb 2026) ergodic streaming encoders up to 245M params, 6.66% average Open ASR WER, CPU-class. Microsoft VibeVoice-ASR-Streaming (3 Sep 2026, 10 languages, hotwords, "who said what") **(details from README only)**. Whisper large-v3-turbo (Oct 2024, ~4x faster, +0.3–2 WER) remains the fallback; faster-whisper has no native streaming; whisper.cpp `stream` re-runs every 0.5 s. No "Whisper v4" exists as of Sept 2026.

| Model | Type | Streaming latency | Accuracy | Languages | License / price |
|---|---|---|---|---|---|
| ElevenLabs Scribe v2 Realtime | Cloud | ~150 ms | Lowest FLEURS WER among low-latency (vendor) | 90+ | Proprietary |
| AssemblyAI Universal-3 Pro Streaming / 3.5 Realtime | Cloud | <300 ms; 534 ms p95 (3.5) | 4.2% WER (Coval) | 6 code-switch + more | Proprietary |
| Deepgram Nova-3 / Flux | Cloud | <300 ms; Flux EOT <300 ms median | 5.26% mean WER (vendor); 25% on Coval hard set | Flux: EN + 10 | $0.0065–0.0078/min (Flux) |
| OpenAI GPT-Realtime-Whisper | Cloud | streaming deltas | n/a | n/a | Realtime API pricing (uncertain) |
| Google Chirp 3 | Cloud | interim results | n/a | 24+ | $0.016/min |
| Mistral Voxtral Realtime (4B) | Open + API | configurable <200 ms | "SOTA open real-time" (vendor) | multilingual | Apache-2.0 |
| NVIDIA Nemotron-3.5-ASR-Streaming-0.6B | Open | 80 ms–1 s configurable | n/a | 40 | Apache-2.0 |
| NVIDIA Parakeet-unified-en-0.6b | Open | 160 ms min | English | 1 | Apache-2.0 |
| Kyutai STT 1B / 2.6B | Open | 0.5 s / 2.5 s delay, semantic VAD | n/a | EN/FR; EN | CC-BY-4.0 |
| Moonshine v2 streaming (≤245M) | Open | Edge/CPU real-time | 6.66% avg Open-ASR WER | English | Permissive |
| Whisper large-v3-turbo (faster-whisper / whisper.cpp) | Open | chunked, ~0.5–4 s | ~+1–2 WER vs v3 | 99 | MIT |

**Picks.** Cloud-first: ElevenLabs Scribe v2 Realtime (or AssemblyAI if you want built-in diarization); Deepgram Flux if you want ASR and turn-taking from one stream. Fully local: NVIDIA Nemotron-3.5-ASR-Streaming-0.6B on any 8 GB+ NVIDIA GPU, Parakeet-unified for English-only; Voxtral Realtime 4B on a 16 GB+ GPU for stronger accuracy; Moonshine v2 / Kyutai STT 1B for CPU or Apple-silicon satellites.

## 2. Text-to-speech

**Cloud.** Independent 2026 measurements show vendor TTFA claims are optimistic: Cartesia Sonic-3 claims 90 ms (Sonic Turbo ~40 ms) but measured ~166–190 ms p50; ElevenLabs Flash v2.5 claims 75 ms, measured ~288 ms. Cartesia Sonic 3 (Oct 2025, SSM architecture, 42 languages) and Sonic 3.5 (GA May 2026) are the raw-latency leaders. ElevenLabs Eleven v3 leads expressiveness (70+ languages, audio tags) but is not the low-latency model. Rime Coda (May 2026), sub-100 ms TTFB, $0.030/min. Hume Octave 2 ~100 ms. Inworld TTS-1.5 ($25/$35 per M chars) and Realtime TTS-2 (<100 ms TTFB). OpenAI gpt-4o-mini-tts ≈ $0.015/min, 13 voices, instruction-steerable. Deepgram Aura-2 ~90 ms, on-prem available. MiniMax Speech 2.6 HD high quality but $100/M chars.

**Local.** Kokoro (82M, Apache-2.0, 8 languages, 54 voices, CPU-capable, no cloning) is the efficiency baseline. Piper lives on at OHF-Voice/piper1-gpl (v1.6.0 July 2026, now GPL-3.0, seeking maintainers). New in 2026: **Qwen3-TTS** (22 Jan 2026, 0.6B/1.7B, Apache-2.0, 10 languages, 97 ms first packet, 3-second cloning); **Kyutai Pocket TTS** (Jan 2026, 100M, MIT, CPU ~6x real-time on M4, ~200 ms first chunk, cloning); **Chatterbox** family (MIT, watermarked): Turbo 350M "sub-200 ms", Nano 110M CPU, Multilingual V3 500M 23+ languages (June 2026); Microsoft VibeVoice-Realtime-0.5B (Dec 2025, MIT, ~300 ms). Orpheus 3B (Apache-2.0, ~200 ms streaming) is the most "human" LLM-style TTS but needs a GPU. Kyutai TTS 1.6B is the streaming engine behind Unmute (~350 ms). Fish Speech / S2 Pro weights are CC-BY-NC. F5-TTS (MIT) is a strong cloner but not streaming-first.

| Model | Where | TTFA (claimed / measured) | Cloning | Local HW | License / price |
|---|---|---|---|---|---|
| Cartesia Sonic 3 / 3.5 | Cloud | 90 ms (Turbo 40) / ~166–190 ms | Yes | — | Free → $4–$299/mo |
| ElevenLabs Flash v2.5 / Eleven v3 | Cloud | 75 ms / ~288 ms | Yes | — | Proprietary |
| Rime Mist v2 / Coda | Cloud | <100 ms TTFB | Yes | — | $0.030/min |
| Hume Octave 2 | Cloud | ~100 ms | Yes | — | tiered |
| Inworld TTS-1.5 / Realtime TTS-2 | Cloud | ~120 ms / <100 ms | Yes | — | $25–35/M chars |
| OpenAI gpt-4o-mini-tts | Cloud | streaming | No | — | ≈$0.015/min |
| Qwen3-TTS 0.6B/1.7B | Local | 97 ms first packet | 3 s | GPU (CUDA) | Apache-2.0 |
| Kyutai Pocket TTS 100M | Local | ~200 ms | Yes | CPU | MIT |
| Chatterbox Turbo / Nano / Multilingual V3 | Local | <200 ms (Turbo) | 5–10 s | small GPU / 8-core CPU | MIT |
| Kokoro 82M | Local | fast, CPU | No | CPU | Apache-2.0 |
| Orpheus 3B | Local | ~200 ms | fine-tune | 8–12 GB GPU | Apache-2.0 |
| VibeVoice-Realtime-0.5B | Local | ~300 ms | No | GPU | MIT |
| Piper (piper1-gpl) | Local | very fast, Pi-class | No | CPU | GPL-3.0 |

**Picks.** Cloud-first: Cartesia Sonic 3.5 for the assistant voice (lowest measured TTFA, streaming, cloning); ElevenLabs Flash v2.5 as second provider. Fully local: Qwen3-TTS-1.7B on the GPU box (best quality/latency/licence combination found); Chatterbox Turbo for a smaller footprint; Kyutai Pocket TTS or Kokoro for CPU-only satellites.

## 3. Speech-to-speech / native audio

**Models.** OpenAI: gpt-realtime (GA Aug 2025) → GPT-Realtime-2 (7 May 2026) → gpt-realtime-2.1 and 2.1-mini (6 July 2026; ≥25% lower p95 latency, better interruption handling). Pricing (third-party, July 2026 list): $32/M audio-in, $64/M audio-out (mini $10/$20); measured $0.06–0.11/min (mini $0.02–0.05) with prompt caching **(uncertain)**. Google: Gemini 3.1 Flash Live (`gemini-3.1-flash-live-preview`, 26 Mar 2026, 90+ languages, affective dialog, proactive audio, barge-in, tool calling); Live audio pricing widely quoted $3/M in, $12/M out (2.5-era) **(uncertain for 3.1)**. Amazon Nova 2 Sonic (Dec 2025, Bedrock) ≈ $0.015/min. xAI Grok Voice Agent API flat $0.05/min. Hume EVI 3 / EVI 4-mini. Kyutai Moshi (open, full-duplex, ~200 ms) remains research-grade; Kyutai's practical answer is **Unmute** (MIT), a cascaded STT+LLM+TTS stack with semantic VAD: ~750 ms on one GPU, ~450 ms with STT/TTS/LLM on separate GPUs, minimum 16 GB VRAM. Sesame open-sourced CSM-1B (Mar 2025) and launched an iOS app May 2026; no public S2S API.

**The trade-off.** S2S wins raw latency; a well-built streaming cascade lands around 500–1,000 ms end-of-speech-to-first-audio, sloppy ones 1.5–3 s. Cascades win on controllability, debuggability, provider choice, and deterministic tool calling — you can see and correct the transcript, run guardrails on text, and swap the LLM (including a local one). S2S cost grows with conversation length because context audio tokens are re-billed. For a home Jarvis whose value is *reliably* calling smart-home tools, the cascade is still the mainstream choice; S2S is worth it for vibe (laughs, tone matching, true full-duplex).

| System | Type | Latency | Tool calling | Cost | Local? |
|---|---|---|---|---|---|
| OpenAI gpt-realtime-2.1 / -mini | Native S2S | p95 ≥25% lower than 2 | Yes | ~$0.06–0.11 / $0.02–0.05 per min | No |
| Gemini 3.1 Flash Live | Native S2S | "lower than 2.5" | Yes | ~$0.005 in + $0.018 out /min (2.5 basis) | No |
| Amazon Nova 2 Sonic | Native S2S | bidirectional streaming | Yes | ~$0.015/min | No |
| xAI Grok Voice Agent | Native S2S | n/a | Yes | $0.05/min flat | No |
| Kyutai Unmute | Open cascade | 450–750 ms | via LLM | GPU 16 GB+ | Yes (MIT) |
| Kyutai Moshi | Open full-duplex | ~200 ms | weak | GPU | Yes |

## 4. Wake word

openWakeWord (Apache-2.0 code; pre-trained models CC-BY-NC-SA 4.0): fully synthetic training; target <0.5 false accepts/hour at <5% false rejects; 15–20 models on one Raspberry Pi 3 core; custom words via Colab; v0.6.0 (Feb 2024) still latest release. microWakeWord (Apache-2.0, OHF-Voice): streaming CNN on ESP32-S3 via TFLite-Micro; the on-device engine in HA Voice PE. Picovoice Porcupine: >97% detection at <1 false alarm/10 h in noise (vendor); custom wake words in minutes; free tier, commercial plans sales-led, third parties cite ~$6,000/yr **(uncertain)**. Community reports put well-trained openWakeWord/microWakeWord models at 0.1–0.5 FA/h in a quiet home.

**Picks.** Cloud-first: Porcupine if you want a "Jarvis" wake word with the least tuning. Fully local: microWakeWord on ESP32-S3 satellites, openWakeWord on Pi/Linux — both free and trainable on "Jarvis" from synthetic data.

## 5. VAD, turn detection, barge-in

Silero VAD v6.x (MIT; 1.2 MB; 32 ms chunks; v6.2 retrained for child voices; **release dating conflicts across sources**) is the de-facto frame-level VAD. WebRTC VAD is no longer competitive alone. The 2026 pattern in LiveKit Agents and Pipecat is identical: Silero for speech/silence + a small end-of-utterance model to decide "done or thinking?" **Pipecat Smart Turn v3.2** (BSD-2, Whisper-Tiny backbone, ~8M params, 8 MB int8, 10–100 ms CPU, 23 languages). **LiveKit** replaced its text EOU models with a unified audio end-of-turn detector (<500 MB RAM; LiveKit Model License; CPU "v1-mini" for self-hosting). Deepgram Flux moves the whole problem into ASR (EagerEndOfTurn / TurnResumed events). Barge-in: gpt-realtime-2.1 and Gemini 3.1 Flash Live handle it natively; cascades implement it as VAD-onset → cancel TTS → flush LLM stream, which is why AEC matters.

| Component | Role | Size / latency | License |
|---|---|---|---|
| Silero VAD v6.2 | Frame VAD | 1.2 MB, <1 ms/chunk | MIT |
| Pipecat Smart Turn v3.2 | Audio EOU | 8 MB, 10–100 ms CPU | BSD-2 |
| LiveKit TurnDetector (audio) | Audio EOU | <500 MB RAM | LiveKit Model License |
| Deepgram Flux | ASR + EOU | EOT <300 ms median | Cloud |
| Kyutai STT semantic VAD | ASR + VAD | 0.5 s delay | CC-BY-4.0 |

## 6. AEC, noise suppression, beamforming, far-field mics

WebRTC AEC3 is the free reference echo canceller for barge-in on a speaker that is also playing TTS. Speex AEC is lighter for Pi-class devices. RNNoise (tiny, BSD) vs DeepFilterNet3 (MIT; 40 ms latency; RTF ≈0.19 single-thread CPU) vs Krisp (commercial, also offers turn-taking). Rule repeated by practitioners: one AEC and one NS in the chain, AEC before NS, never stack suppressors. Hardware XMOS route offloads AEC/beamforming and is the most reliable far-field barge-in path: Seeed reSpeaker XVF3800 (4-mic circular, AEC/AGC/DoA/beamforming/NS/dereverb, 5 m 360° pickup; ~$35–60 class **(uncertain)**), HA Voice PE ($59, XMOS XU316 2-mic).

**Pick (both stacks):** XVF3800 or HA Voice PE so echo cancellation and beamforming happen in silicon; WebRTC AEC3 + DeepFilterNet on the hub only when using plain USB mics.

## 7. Speaker identification / diarization

pyannote.audio 4.0 (MIT) community-1: DER 11.7% AISHELL-4, 20.2% DIHARD-3, 11.2% VoxConverse. pyannoteAI precision-2 (paid) ~28% better and the only pyannote model with voiceprints. Embedding backbones for household "who is speaking": SpeechBrain **ECAPA-TDNN** (10.7% DER in a pyannote fine-tune study vs 12.0% NVIDIA TitaNet), Resemblyzer (used by the EuleMitKeule speaker-recognition Home Assistant add-on — MIT, CPU, maps voices to HA users), WeSpeaker. NVIDIA Streaming Sortformer is the open streaming diarizer. Cloud speaker-ID is thinning: Azure Speaker Recognition retired Sept 2025, Amazon Connect Voice ID exited May 2026; remaining: AssemblyAI streaming diarization, pyannoteAI API, Picovoice Eagle (on-device). Home Assistant has no native speaker recognition yet (open feature request).

**Picks.** Cloud-first: AssemblyAI streaming diarization for "who said what" + local ECAPA-TDNN enrollment for household members. Fully local: ECAPA-TDNN embeddings (cosine match against enrolled family voiceprints) on each wake-word utterance; pyannote 4 only for multi-party transcripts.

## Recommended stacks (summary)

**(a) Cloud-first:** XVF3800/HA Voice PE (HW AEC) → microWakeWord/Porcupine → Deepgram Flux *or* Scribe v2 Realtime + Smart Turn v3 → LLM with tools → Cartesia Sonic 3.5 (fallback ElevenLabs Flash v2.5) → optional gpt-realtime-2.1-mini / Gemini 3.1 Flash Live "conversation mode". Expect ~600–900 ms end-of-speech-to-first-audio in practice.

**(b) Fully local (one 16–24 GB NVIDIA GPU + ESP32-S3 satellites):** XVF3800 → microWakeWord → Silero VAD v6.2 + Smart Turn v3.2 → Nemotron-3.5-ASR-Streaming-0.6B (or Parakeet-unified for English) → local LLM → Qwen3-TTS-1.7B (Chatterbox Turbo / Pocket TTS lighter) → ECAPA-TDNN speaker ID. Kyutai Unmute's 450–750 ms is a realistic target.

**Biggest uncertainties:** exact 2026 vendor prices for OpenAI/Google, Picovoice commercial pricing, Silero release dating, XVF3800 street price, and the true accuracy ranking between Deepgram and AssemblyAI.

## Sources
- https://deepgram.com/learn/best-speech-to-text-apis-2026 · https://www.coval.ai/blog/best-speech-to-text-providers-in-2026-independent-benchmarks-and-how-to-choose/ · https://gradium.ai/content/stt-api-benchmark-2026-latency-accuracy
- https://www.assemblyai.com/blog/best-api-models-for-real-time-speech-recognition-and-transcription · https://elevenlabs.io/blog/scribe-v2-realtime-in-elevenlabs-agents · https://mistral.ai/news/voxtral-transcribe-2/
- https://github.com/NVIDIA-NeMo/Speech · https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b · https://huggingface.co/nvidia/parakeet-unified-en-0.6b/discussions/7
- https://github.com/kyutai-labs/delayed-streams-modeling · https://arxiv.org/abs/2602.12241 · https://github.com/microsoft/VibeVoice · https://github.com/SYSTRAN/faster-whisper · https://github.com/ggml-org/whisper.cpp · https://github.com/huggingface/open_asr_leaderboard
- https://deepgram.com/learn/introducing-flux-conversational-speech-recognition · https://www.llmreference.com/provider/deepgram/flux-asr
- https://futureagi.com/blog/best-text-to-speech-providers-2026/ · https://inworld.ai/resources/best-voice-ai-tts-apis-for-real-time-voice-agents-2026-benchmarks · https://texttolab.com/blog/cartesia-pricing · https://www.rime.ai/pricing · https://dev.hume.ai/docs/text-to-speech-tts/overview · https://tokenmix.ai/blog/gpt-4o-mini-tts-cheapest-tts-api-2026
- https://github.com/QwenLM/Qwen3-TTS · https://github.com/kyutai-labs/pocket-tts · https://github.com/resemble-ai/chatterbox · https://github.com/canopyai/Orpheus-TTS · https://github.com/OHF-Voice/piper1-gpl · https://www.tryspeakeasy.io/blog/open-source-text-to-speech-2026
- https://community.openai.com/t/new-realtime-models-on-the-api-gpt-realtime-2-1-and-gpt-realtime-2-1-mini/1385896 · https://hackernoon.com/openai-realtime-api-pricing-in-2026-real-world-data-from-4000-measured-sessions · https://www.layer3labs.io/guides/openai-realtime-api-pricing
- https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-1-flash-live/ · https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-live-preview · https://aws.amazon.com/about-aws/whats-new/2025/12/amazon-nova-2-sonic-real-time-conversational-ai · https://www.hume.ai/blog/introducing-evi-3
- https://github.com/kyutai-labs/unmute · https://futureagi.com/blog/cascaded-voice-ai-vs-speech-to-speech-2026/ · https://deepgram.com/learn/speech-to-speech-vs-cascade-voice-agent-architecture
- https://github.com/dscripka/openWakeWord · https://github.com/OHF-Voice/micro-wake-word · https://esphome.io/components/micro_wake_word/ · https://github.com/Picovoice/porcupine
- https://github.com/snakers4/silero-vad/releases · https://github.com/pipecat-ai/smart-turn · https://huggingface.co/pipecat-ai/smart-turn-v3 · https://docs.livekit.io/agents/logic/turns/turn-detector/
- https://www.forasoft.com/learn/ai-for-video-engineering/articles-ai/real-time-noise-suppression-krisp-rnnoise-deepfilternet · https://wiki.seeedstudio.com/respeaker_xvf3800_introduction/ · https://www.home-assistant.io/voice-pe/
- https://github.com/pyannote/pyannote-audio · https://www.pyannote.ai/blog/community-1 · https://github.com/EuleMitKeule/speaker-recognition · https://picovoice.ai/blog/state-of-speaker-recognition/ · https://github.com/rhasspy/wyoming
