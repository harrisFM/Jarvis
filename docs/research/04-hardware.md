# Research Note 04 — Hardware (central server and room satellites)

Research date: 2026-09-11. Compiled from web sources; figures are as found in sources. Items marked **(uncertain)** are single-source, conflicting, or inferred and should be re-verified before purchase.

## 1. Central inference server

### Key physics
For a single household conversation, decode speed is bounded by memory bandwidth (every weight is read once per token), while prefill (reading the prompt) is compute-bound. DGX Spark is "hard-bound by LPDDR5x bandwidth" (273 GB/s); Strix Halo is ~256 GB/s theoretical / ~215 GB/s measured. MoE models (gpt-oss-120b, Qwen3-30B-A3B, Qwen 3.5 35B-A3B) are therefore the sweet spot for unified-memory boxes; dense 70B models are slow on all of them.

### 1a. NVIDIA DGX Spark (GB10, 128 GB LPDDR5x, 273 GB/s) and partner variants
- **Price:** Founders Edition raised from $3,999 to **$4,699** in Feb 2026 (memory supply). Partners: ASUS Ascent GX10 from **$3,999** (Aug 2026; other configs $4,699/$5,999); Dell Pro Max GB10 **$3,699 (2 TB) / $3,999 (4 TB)** per reviews; Lenovo ThinkStation PGX 1 TB seen at **$5,849**. Also Acer Veriton GN100, Gigabyte AI TOP ATOM, HP ZGX Nano, MSI EdgeXpert MS-C931.
- **LLM performance (llama.cpp, Oct 2025, ggml-org discussion #16578):**
  - gpt-oss-120b MXFP4: **prefill 1,956 t/s, decode 60.6 t/s** at depth 0 → 1,027 / 40.6 t/s at 32k context.
  - gpt-oss-20b: ~2,100 pp / 62-65 tg. Qwen3-Coder-30B Q8: ~1,750 pp / 46-48 tg.
  - Qwen3 32B dense: 762 pp / **10.7 tg**; Qwen3 8B: 3,167 pp / 43.7 tg; Qwen3-30B MoE: 2,541 pp / 89 tg.
  - Qwen3.8-27B (Aug 2026 thread): 15-18 t/s in llama.cpp, ~38 t/s reported with SGLang — framework choice matters.
  - Dense 70B: Llama-3.3-70B FP8 ~3 t/s reported; bandwidth math caps Q4 70B around 6-7 t/s. Claims of "35-45 t/s for 70B" are **not credible (uncertain/wrong)**.
- **Issues:** idle initially ~37 W, reduced to **22-25 W** by firmware update; threads about performance capping near 100 W; slow model loading on non-DGX-OS distros (mitigated by `GGML_CUDA_ENABLE_UNIFIED_MEMORY=1`).

### 1b. NVIDIA DGX Station (GB300)
Shipping since June 2026 (ASUS, Dell, HP, Gigabyte, MSI, Supermicro) at roughly **$80k-$125k**. Out of scope for a home.

### 1c. Apple Mac Studio
- **New lineup (announced Aug 25, 2026):** **M5 Max from $2,499** (up to 128 GB, **614 GB/s**), **M5 Ultra from $5,499** (80-core GPU, up to **512 GB**). GA Sept 22, 2026; 512 GB configs expected late October. M5 Ultra bandwidth not stated **(uncertain; likely ~2x Max)**. No M4 Ultra was ever released.
- **M3 Ultra (previous gen, the one with public LLM benchmarks):** ~800 GB/s, up to 512 GB. DeepSeek-V3-0324 4-bit via MLX: **>20 t/s**; DeepSeek R1 671B ~17-18 t/s; same model in llama.cpp ~6.2 t/s with very slow prompt processing. Qwen 3.5 35B-A3B 8-bit MLX: 80+ t/s. Whole-system power under 200 W during 671B inference; **idle 9 W** (Apple spec). MLX is 15-25% faster than llama.cpp on Apple silicon; prompt processing is the weak spot versus NVIDIA.

### 1d. AMD Strix Halo (Ryzen AI Max+ 395, 128 GB) mini PCs
- **Performance:** gpt-oss-120b **~31 t/s** decode; Qwen3-30B-A3B 70-100 t/s; dense 70B Q4 **~5 t/s**; Qwen3.8-27B ~20 t/s via Ollama on Beelink GTR9 Pro. Vulkan is the everyday backend; ROCm for long-context. Prefill figures not fetched **(uncertain)**.
- **Prices (volatile, LPDDR5x costs):** Framework Desktop 128 GB **$3,449** (was $1,999 at Feb 2025 reveal); Framework announced a Ryzen AI Max+ Pro 495 board with **192 GB**. GMKtec EVO-X2 128 GB/2 TB list $2,799, promo **$1,999**. Beelink GTR9 Pro launched $1,985, currently **$4,349**. HP Z2 Mini G1a ~$3,300-3,649.
- **Idle:** Framework Desktop **12.5 W** (Phoronix).

### 1e. Discrete-GPU builds
| GPU | VRAM / bandwidth | Price (Sept 2026) | Power | Notes |
|---|---|---|---|---|
| RTX 5090 | 32 GB / 1.79 TB/s | **$5,069-5,799 new**, used ~$3,590 (>2x the $1,999 MSRP) | 575 W; idle 30-46 W; 38-42 dBA load | Fastest single-user for models ≤32 GB; cannot hold 70B/120B |
| RTX PRO 6000 Blackwell | 96 GB / 1.79 TB/s | **$7,999-9,449** | 600 W; Max-Q variant 300 W blower | Holds gpt-oss-120b in one card |
| RTX 4090 | 24 GB | $2,755 new; used $1,500-2,268 | 450 W | |
| RTX 3090 (used) | 24 GB / 936 GB/s | **$700-1,050** | 350-400 W each | "Value king"; two cards = 48 GB for 70B Q4 |
| RTX A6000 (used) | 48 GB | $2,600-3,800 | 300 W | Quiet blower, 2-slot |
| Intel Arc Pro B60 | 24 GB / 456 GB/s | street **$660-800** | ~120-200 W (unverified) | vLLM optimized; less mature stack |
| Tenstorrent Blackhole p150 | 32 GB | **$1,399** | — | Software immaturity; not recommended |

### 1f. Comparison for a household assistant (1 concurrent conversation + STT/TTS resident)
| Option | Cost | Largest sensible model | Decode t/s (sourced) | Idle W | Noise | Verdict |
|---|---|---|---|---|---|---|
| Used RTX 3090 in existing PC | $700-1,050 | 30B-class Q4 + Whisper + TTS | fast (no exact figure found) | ~30 W GPU + host | fan noise | Best $/perf entry |
| Intel Arc Pro B60 | $660-800 | ~38B Q4 | comparable (vendor claim) | — | — | Budget alternative |
| Strix Halo 128 GB | $2,000-3,450 | gpt-oss-120b, Qwen3-235B Q3 (slow) | 31 (120B MoE), 70-100 (30B MoE), ~5 (70B dense) | 12.5 W | quiet | Best value 120B-class box |
| DGX Spark / GX10 / Dell GB10 | $3,699-4,699 | gpt-oss-120b, 200B-class MoE Q4 | 60 (120B MoE), 89 (30B MoE), 10.7 (32B dense) | 22-25 W | quiet | 2x Strix Halo decode, ~5x prefill; CUDA |
| Mac Studio M5 Max 128 GB | from $2,499 (+128 GB upcharge) | 120B MoE | not yet benchmarked (614 GB/s) | ~10 W | near silent | Watch benchmarks after Sept 22 |
| Mac Studio M5 Ultra 512 GB | $5,499 base; 512 GB TBD (M3 Ultra 512 GB ~$9.5k, uncertain) | 671B-class MoE Q4 | M3 Ultra: >20 (671B MLX) | 9 W | near silent | Biggest models, weakest prefill |
| RTX PRO 6000 build | $10-13k | gpt-oss-120b full speed, 70B Q8 | fastest single card | 60-100 W system | blower | Fastest, priciest, hottest |

## 2. Edge satellites (in-room voice endpoints)

| Device | Price | Mics / DSP | Speaker | Wake word | Notes |
|---|---|---|---|---|---|
| **HA Voice Preview Edition** | $59 street / $69 MSRP | XMOS XU316 (AEC, NS, AGC, beamforming); ESP32-S3 16 MB flash / 8 MB PSRAM | small internal + 3.5 mm out | microWakeWord on-device | Official reference; still shipping 2026; **no successor found** |
| **FutureProofHomes Satellite1 / 1.1** | dev kit $79.99; assembled ~$135 (often backordered) | 4-mic array, XMOS XU316 | 25 W amp, headphone jack | microWakeWord | Adds temp/humidity/lux/presence sensors; best all-in-one |
| **Seeed ReSpeaker Lite** | $32 | 2-mic, XU316 | amp for external speaker | microWakeWord | Basis of DIY **Koala Satellite** |
| **Seeed ReSpeaker XVF3800** | $60 | 4-mic, XVF3800 | — | via ESPHome | Better far-field; also USB array variant |
| **ESP32-S3-BOX-3** | $60 | 2-mic, no XMOS | small | microWakeWord | Touchscreen; degrades in noisy rooms |
| **M5Stack Atom Echo / EchoS3R (2026)** | $14 | 1 mic, no AEC | tiny | HA-side | Testing only |
| **Raspberry Pi 5 + ReSpeaker USB Mic Array (XVF3000)** | Pi ~$80 + array | 4-mic, hardware AEC, barge-in during music | any USB/HDMI | openWakeWord / microWakeWord (OHF linux-voice-assistant) | Legacy 2-Mic HAT has Pi 5 driver issues |
| **Jetson Orin Nano Super** | **$399** (was $249; NVIDIA raised Jetson prices up to 101% in July 2026) | any USB array | — | wake word + whisper.cpp + Piper locally | Mid-tier satellite; AGX Thor dev kit $5,499 is overkill |
| Repurposed Echo/Nest | $0-30 | | | | Echo Show 5/8 Gen 1 jailbroken; Echo Show 5 Gen 2 jailbroken Jan 2026; Onju Voice unfinished; **MiciMike** drop-in PCB for Google Home Mini crowdfunding Apr 2026 |
| Desktop/laptop client | free | | | openWakeWord/microWakeWord | **OHF-Voice linux-voice-assistant**: any x64/ARM64 Linux, speaks ESPHome protocol, auto-discovered by HA |
| Wearables | — | | | | No HA-native AirPods/Apple Watch/Meta glasses input path found **(not available)** |

**Far-field ranking:** XMOS-equipped devices (Voice PE, Satellite1, ReSpeaker Lite/XVF3800) handle echo cancellation while music plays; ESP32-S3-BOX-3 and Atom Echo lack a DSP. Speaker quality: Satellite1 (25 W amp) > Voice PE 3.5 mm to external speaker > built-ins.

**Speech models on the brain:** Whisper large-v3 ~3 GB VRAM FP16; large-v3-turbo ~4x faster at 1-2 WER points cost; faster-whisper INT8 25-30x real-time on GPU. **NVIDIA Parakeet-TDT 0.6B** tops the Open ASR leaderboard (~6.05% vs 7.44% Whisper-v3) and runs ~30x real-time even on CPU INT8. Piper TTS was **archived Oct 6, 2025** (still works as a Wyoming add-on); Kokoro-82M with streaming `kokoro-wyoming` is the current community favorite. HA's Speech-to-Phrase is the low-latency fallback for fixed commands.

## 3. Networking and infrastructure
- **VLANs:** MAIN + IOT VLAN pattern; ESPHome satellites rely on mDNS, so an **mDNS reflector** is required across VLANs; duplicate device names break discovery.
- **Wi-Fi vs Ethernet/PoE:** all ESP32-S3 satellites are Wi-Fi only; Pi 5 and Jetson can use Ethernet/PoE HATs. No benchmark found for Wi-Fi vs Ethernet satellite latency.
- **Virtualization:** Proxmox **LXC GPU passthrough** favored for sharing one GPU across Ollama/Whisper/Frigate (near-native perf); a VM is simpler for a single instance. Unified-memory boxes generally run bare-metal Docker.
- **UPS/backups:** size for the brain's idle + peak (Strix Halo/Spark ~150-250 W peak; 5090 system ~650 W).

## 4. Vision, presence and displays
- **Frigate detectors (official docs):** Coral EdgeTPU, Hailo-8/8L, OpenVINO (Intel CPU/iGPU/NPU), ONNX, Apple Silicon, TensorRT (Jetson); community: MemryX MX3, Rockchip RKNN. Two 2026 guides say **Coral is no longer recommended for new installs** (driver archived April 2026 claim) — Frigate's own docs don't say this **(uncertain)**. Consensus 2026: **Intel N100/N150 mini PC (~$309-339) with OpenVINO** for 2-6 cameras; Hailo-8L/8 when scaling.
- **mmWave presence:** Aqara FP2 **$58-83**; Everything Presence One **$57-64**; Everything Presence Lite **$34-38**; Apollo MTR-1.
- **Displays:** Inkplate 10 (9.7" e-ink), Inkplate 6FLICK, XIAO ePaper Panel 7.5" **$127.99**, TRMNL X **$189 pre-order**, SONOFF NSPanel Pro; jailbroken Echo Shows as wall dashboards.

## 5. Cloud/hybrid alternatives (Sept 2026)
| GPU | On-demand $/hr | 24/7 month (720 h) |
|---|---|---|
| RTX 5090 | $0.35 (cheapest), Vast median $0.53, spot $0.15 | $252 / $382 / $108 |
| RTX 4090 | RunPod $0.69 secure / $0.34 community | $497 / $245 |
| H100 SXM | Vast $1.49-2.13, RunPod $3.29, Lambda $3.99-4.29 | $1,073-3,089 |

A 24/7 rented 5090 costs ~$3,000-4,600/yr versus ~$5,200 to buy one, or ~$2,000-3,450 for a Strix Halo box that idles at 12.5 W (≈$20/yr electricity at $0.18/kWh). Ownership wins above ~60% sustained utilization; a household assistant is on 24/7 but utilized <5% — the always-on requirement favors owning a low-idle box. Hybrid (local STT/TTS/wake word + cloud LLM) keeps raw audio at home while sending text.

## 6. Three build tiers

### Budget ($500-1,500)
- Brain: existing PC + **used RTX 3090 ($700-1,050)** or **Intel Arc Pro B60 ($660-800)**; runs Qwen3-30B-A3B/gpt-oss-20b-class + Whisper-turbo + Kokoro. Hybrid: cloud LLM for hard queries.
- Satellites: 2x **HA Voice PE ($118)**.
- Sensors: 1-2x Everything Presence Lite ($34-38).
- Total ≈ **$900-1,400**. Idle ~40-80 W.

### Prosumer ($3-6k)
- Brain: **Strix Halo 128 GB (~$2,000-3,449)** for gpt-oss-120b at ~31 t/s at 12.5 W idle; or **DGX Spark partner box ($3,699-4,699)** for 60 t/s and ~2k t/s prefill; or wait for **M5 Max 128 GB** benchmarks.
- Satellites: 4-6x Voice PE or 2x Satellite1 + 3x Voice PE ≈ $450-600.
- Vision: N150 mini PC ($309-339) for Frigate/OpenVINO + 2-4 PoE cameras; 3x presence sensors (~$180).
- Infra: managed PoE switch with VLANs + mDNS reflector, small UPS.
- Total ≈ **$3,500-6,000**.

### No-compromise ($10-20k+)
- Brain: **Mac Studio M5 Ultra 512 GB** (~$9-10k, uncertain) for 671B-class MoE at 9 W idle; or **RTX PRO 6000 Blackwell Max-Q build** (~$10-13k) for the fastest 120B-class decode and prefill; or 2x DGX Spark linked via ConnectX.
- Satellites: Satellite1 in every room (6-8 x ~$135 ≈ $1,100) + Linux clients on desktops.
- Vision: Frigate on Hailo-8 or TensorRT with 6-8 cameras (~$1,500-2,500).
- Displays: e-ink per floor, jailbroken Echo Shows as touch dashboards.
- Total ≈ **$12,000-20,000+**.

### Bottom line
1. For one low-latency conversation plus resident STT/TTS, a **DGX Spark-class box is the best balance** (60 t/s on gpt-oss-120b, ~2k t/s prefill, 22-25 W idle, CUDA). Strix Halo is the value pick at roughly half the price and half the decode speed. Mac Studio wins on idle power and max model size but loses on prompt processing.
2. Avoid dense 70B on any unified-memory box (3-10 t/s); prefer MoE.
3. For satellites, only buy XMOS-equipped hardware.
4. Coral is a dead end for new Frigate builds; use Intel OpenVINO or Hailo.
5. Jetson prices jumped 60-100% in July 2026; Pi 5 + USB XVF3000 array is cheaper for local wake-word/STT.

## Sources
- https://github.com/ggml-org/llama.cpp/discussions/16578
- https://github.com/ggml-org/llama.cpp/discussions/27080
- https://github.com/DandinPower/llama.cpp_bench/blob/main/dgx_spark/report.md
- https://forums.developer.nvidia.com/t/trouble-with-llama-70b-3-3-instruct-fp8-model-at-3-tokens-per-second/360643
- https://forums.developer.nvidia.com/t/2-23-2026-price-change-announcement/361713
- https://www.techpowerup.com/346833/nvidia-raises-dgx-spark-pricing-to-usd-4-700
- https://www.tomshardware.com/tech-industry/artificial-intelligence/nvidia-dgx-spark-update-cuts-idle-power-by-32-percent-or-more-hot-plug-detection-on-connectx-nic-makes-for-a-more-efficient-ai-workstation
- https://spark.enverge.ai/blog/dgx-spark-prefill-vs-decode
- https://eshop.asus.com/us/ascent-gx10.html
- https://www.storagereview.com/review/dell-pro-max-with-gb10-review
- https://www.servethehome.com/nvidia-dgx-station-systems-available-at-last-gb300-gb200-workstations-for-your-desktop/
- https://9to5mac.com/2026/08/25/apple-unveils-next-generation-mac-studio-with-m5-max-and-m5-ultra/
- https://www.macrumors.com/2026/08/25/mac-studio-m5-ultra-512gb-ram-october/
- https://venturebeat.com/ai/deepseek-v3-now-runs-at-20-tokens-per-second-on-mac-studio-and-thats-a-nightmare-for-openai
- https://www.hardware-corner.net/mac-studio-m3-ultra-deepseek-llamacpp/
- https://willitrunai.com/blog/qwen-3-5-mlx-apple-silicon-guide
- https://kyuz0.github.io/amd-strix-halo-toolboxes/
- https://datahardware.ai/blog/strix-halo-tokens-per-second-2026
- https://www.phoronix.com/review/framework-desktop-power/5
- https://www.notebookcheck.net/Framework-launches-world-s-first-mini-ITX-desktop-PC-with-Ryzen-AI-Max-Pro-495-and-192-GB-RAM.1349336.0.html
- https://www.gmktec.com/blog/gmktec-evo-x2-special-140-off-discount-lowest-prices-ever-all-variants-applicable
- https://www.storagereview.com/review/hp-z2-mini-g1a-review-running-gpt-oss-120b-without-a-discrete-gpu
- https://videocardprices.com/card/nvidia-rtx-5090/
- https://www.techpowerup.com/review/nvidia-geforce-rtx-5090-founders-edition/46.html
- https://www.thundercompute.com/blog/nvidia-rtx-pro-6000-pricing
- https://www.runaihome.com/blog/rtx-pro-6000-blackwell-local-ai-2026/
- https://www.xda-developers.com/used-rtx-3090-value-king-local-ai/
- https://www.fitmyllm.com/gpu/arc-pro-b60
- https://tenstorrent.com/en/newsroom/tenstorrent-launches-blackhole-developer-products-at-tenstorrent-dev-day
- https://www.home-assistant.io/voice-pe/
- https://botmonster.com/smart-home/home-assistant-voice-preview-edition-review/
- https://www.cnx-software.com/2025/05/16/satellite1-dev-kit-is-an-home-assistant-compatible-diy-voice-assistant-with-esp32-s3-module-xmos-xu316-audio-processor/
- https://futureproofhomes.net/products/satellite1-pcb-dev-kit
- https://openelab.io/blogs/learn/home-assistant-local-voice-assistant-hardware
- https://www.smarthomeexplorer.com/guides/best-home-assistant-voice-satellite-2026
- https://github.com/formatBCE/Koala-Satellite
- https://github.com/rhasspy/wyoming-satellite
- https://github.com/OHF-Voice/linux-voice-assistant
- https://www.home-assistant.io/voice_control/about_wake_word/
- https://www.cnx-software.com/2026/07/22/nvidia-increases-the-price-of-jetson-modules-and-devkits-by-up-to-101/
- https://hackaday.com/2026/01/02/jailbreaking-the-amazon-echo-show/
- https://www.cnx-software.com/2026/04/29/micimike-open-source-drop-in-pcb-converts-google-home-mini-into-a-local-voice-assistant/
- https://snailtext.app/blog/whisper-vs-parakeet-tdt/
- https://community.home-assistant.io/t/streaming-tts-for-kokoro-kokoro-wyoming-assist-speaks-before-the-llm-finishes/1024691
- https://github.com/blakeblackshear/frigate/blob/dev/docs/docs/configuration/object_detectors.md
- https://terminalbytes.com/best-hardware-for-frigate-nvr-2026/
- https://hometechops.com/cameras/coral-vs-hailo-vs-intel-npu
- https://smarthomefieldguide.com/blog/best-presence-sensor-2026/
- https://community.home-assistant.io/t/howto-use-esphome-in-a-vlan-setup/991310
- https://www.xda-developers.com/gpu-passthrough-to-lxcs-beats-vms/
- https://getdeploying.com/gpus/nvidia-rtx-5090
- https://tech-insider.org/runpod-vs-lambda-vs-vast-ai-2026/
- https://www.kunalganglani.com/blog/local-llm-cost-breakeven
