# Real-Application Test Set (`[REAL]`)

**Provenance:** `[REAL]` Live Host Application Processes (ffmpeg libopus, curl HTTP/TLS)  
**Status:** Dedicated Test-Only Set (Never used for training or tuning)  
**Total Sessions:** 40 (10 per class)  

### Application Composition
1. **Realtime (10 sessions):** Real live Opus voice audio encoded and streamed by `ffmpeg` (`-c:a libopus -f rtp`) over UDP at bitrates 24–48 kbps.
2. **Stream (10 sessions):** Real HTTP video chunk requests executed by `curl` fetching `.m4s` segment chunks from a local media endpoint.
3. **Bulk (10 sessions):** Real high-volume binary downloads executed by `curl` streaming multi-megabyte payloads over TCP.
4. **Other (10 sessions):** Real REST API JSON queries executed by `curl` with realistic HTTP request-response-close cycles.

### Privacy & Ethics Note
* Generated using local testing endpoints and synthetic audio source `aevalsrc`.
* Zero private user payloads or personal data captured; headers-only extraction (22 Zero-DPI features).
