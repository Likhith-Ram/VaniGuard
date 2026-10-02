# VaniGuard — Full-Stack Architecture Audit

> **Scope:** Backend (FastAPI + SQLAlchemy + ONNX), ML pipeline (librosa + NumPy), Frontend (Next.js 16 + React 19 + Recharts + Framer Motion), WebSocket streaming, Database models, Docker.
> **Severity:** 🔴 Critical · 🟠 High · 🟡 Medium · 🟢 Low

---

## Table of Contents
1. [Security Vulnerabilities](#1-security-vulnerabilities)
2. [API & Backend Bottlenecks](#2-api--backend-bottlenecks)
3. [ML Pipeline Performance](#3-ml-pipeline-performance)
4. [Database & Query Inefficiencies](#4-database--query-inefficiencies)
5. [WebSocket Streaming Issues](#5-websocket-streaming-issues)
6. [Frontend Performance & State](#6-frontend-performance--state)
7. [Bundle Size & Dependencies](#7-bundle-size--dependencies)
8. [Reliability & Error Handling](#8-reliability--error-handling)
9. [Scalability Issues](#9-scalability-issues)
10. [Accessibility (A11y)](#10-accessibility-a11y)
11. [Concurrency & Race Conditions](#11-concurrency--race-conditions)
12. [Summary Table](#12-priority-summary-table)

---

## 1. Security Vulnerabilities

### 🔴 CRIT-01 — Wildcard CORS (`allow_origins=["*"]` + credentials)
**File:** [`api/main.py:37-43`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/main.py#L37-L43)

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # ← any origin
    allow_credentials=True,  # ← plus cookies/auth headers
    allow_methods=["*"],
    allow_headers=["*"],
)
```
`allow_credentials=True` combined with `allow_origins=["*"]` is **explicitly forbidden by the CORS spec** and is rejected by browsers in practice — but it signals a complete absence of origin validation. Any website can make credentialed cross-origin requests. Should be scoped to the specific Next.js origin.

---

### 🔴 CRIT-02 — Hardcoded Database Credentials in Source & Docker
**Files:** [`api/core/database.py:7`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/core/database.py#L7), [`docker-compose.yml:7`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/docker-compose.yml#L7)

```python
POSTGRES_PASSWORD = os.getenv("VANIGUARD_DB_PASSWORD", "vanipass123")
```
```yaml
POSTGRES_PASSWORD: vanipass123
```
Plaintext password is committed to version control. Anyone with repo access has the production DB password. Use a secrets manager or `.env` file excluded from git.

---

### 🔴 CRIT-03 — No Authentication on Any Endpoint
**Files:** `api/main.py`, `api/routes/users.py`

Every route — `/analyze`, `/api/scans/history`, `/api/stats`, `/api/users/`, `/stream` — is completely unauthenticated. This means:
- Anyone on the internet can POST audio and consume ONNX inference compute (resource exhaustion).
- Anyone can read full scan history (data leak).
- Anyone can enumerate/delete users.

No JWT, no API key, no rate limiting.

---

### 🟠 HIGH-01 — No File Upload Validation
**File:** [`api/main.py:60-61`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/main.py#L60-L61)

```python
audio_bytes = await file.read()  # reads entire file into RAM
ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else "wav"
```
- **No size limit**: a 4 GB upload will be fully buffered in memory before any validation.
- **Extension from filename only**: trivially spoofed. MIME type and magic-byte validation are absent.
- **No memory cap**: a malicious user can exhaust server RAM by sending concurrent huge uploads.

Fix: enforce `Content-Length` header check, use `UploadFile.read(max_size)`, validate magic bytes.

---

### 🟠 HIGH-02 — Hardcoded `API_BASE` / WebSocket URLs on the Client
**Files:** [`frontend/src/lib/api.ts:3`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/lib/api.ts#L3), [`frontend/src/components/LiveDetector.tsx:14`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/components/LiveDetector.tsx#L14), [`frontend/src/components/AuditLogs.tsx:14`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/components/AuditLogs.tsx#L14), [`frontend/src/hooks/useAudioStream.ts:61`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/hooks/useAudioStream.ts#L61)

`http://localhost:8000` appears **four times** independently across the codebase. This will silently break in every non-localhost environment (deployed preview, production, CI). It should be a single `NEXT_PUBLIC_API_BASE` env variable.

---

### 🟠 HIGH-03 — OTP Is Client-Side Only (Security Theater)
**File:** [`frontend/src/components/LiveDetector.tsx:22-40`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/components/LiveDetector.tsx#L22-L40)

```tsx
const code = String(Math.floor(100000 + Math.random() * 900000));
```
The OTP is generated, stored, and "verified" entirely in the browser. Anyone who opens DevTools can read or bypass it. A real OTP flow requires server-side generation and delivery via SMS/email. Currently this is pure UX theater with zero security value.

---

### 🟠 HIGH-04 — Plaintext WebSocket (`ws://`, not `wss://`)
**File:** [`frontend/src/hooks/useAudioStream.ts:61`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/hooks/useAudioStream.ts#L61)

```ts
wsRef.current = new WebSocket("ws://localhost:8000/stream");
```
Audio data (including voice) is transmitted in cleartext. Should be `wss://` in all non-local environments. This is a voice-fraud protection product — the irony of transmitting voice without TLS is severe.

---

### 🟡 MED-01 — No Rate Limiting on `/analyze`
Heavy ONNX inference (CPU-bound librosa + model run) is unmetered. A client can script rapid parallel uploads, saturating CPU and memory on the host.

---

## 2. API & Backend Bottlenecks

### 🔴 CRIT-04 — Synchronous (CPU-Blocking) ONNX Inference Inside Async Handler
**File:** [`api/main.py:63-64`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/main.py#L63-L64)

```python
mel_norm, mel_tensor, duration_s = preprocess_audio(audio_bytes, ext)  # ← CPU-bound
prob_ai = run_inference(session, mel_tensor)                             # ← CPU-bound
```
Both are **pure synchronous CPU operations** called directly inside an `async def` FastAPI route. This **blocks the entire async event loop** for the entire duration of librosa processing + ONNX inference. While one request is being processed, no other request can be accepted or responded to.

**Fix:** wrap in `asyncio.get_event_loop().run_in_executor(None, ...)` or use a dedicated `ThreadPoolExecutor`. Alternatively switch to a task queue (Celery/ARQ) for long-running inference.

---

### 🔴 CRIT-05 — `audio_bytes = await file.read()` Loads Entire File Into RAM
**File:** [`api/main.py:60`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/main.py#L60)

For a 10 MB audio file: the full bytes sit in memory for the duration of preprocessing. With 10 concurrent uploads that's 100 MB just for raw bytes, before any numpy arrays are allocated. The mel spectrogram pipeline then allocates additional large numpy arrays. Add the lack of upload size limits (CRIT-03) and this is a straightforward memory-exhaustion vector.

---

### 🟠 HIGH-05 — Double `commit()` Per `/analyze` Request
**Files:** [`api/main.py:77-83`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/main.py#L77-L83), [`api/repositories/scan_repository.py:29`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/repositories/scan_repository.py#L29), [`api/core/database.py:38`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/core/database.py#L38)

`ScanRepository.create_scan()` calls `await self.session.commit()` explicitly. Then `get_db()` calls `await session.commit()` again in its `finally` block. This is two round-trips to PostgreSQL per request and can cause subtle state issues if the second commit sees a dirty session after the first.

**Fix:** Remove the `commit()` from the repository and let the `get_db()` context manager own the transaction lifecycle.

---

### 🟠 HIGH-06 — Two Separate DB Queries for History + Count (N+1 Pattern)
**File:** [`api/main.py:135-145`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/main.py#L135-L145)

```python
result = await db.execute(query)  # Query 1: fetch rows
count_result = await db.execute(select(func.count()).select_from(AudioScan))  # Query 2: full table count
```
These are sequential round-trips. The `COUNT(*)` on the full `audio_scans` table will grow with data and is recomputed on every call to `/api/history`. Use a single `SELECT count(*) OVER() AS total_count, ...` window function, or use `COUNT(*) FILTER(...)` in the same query.

---

### 🟠 HIGH-07 — `language` Column Has No Index
**File:** [`api/models/models.py:70`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/models/models.py#L70)

```python
language = Column(String(20), nullable=True)
```
The `/api/scans/history` endpoint filters by `language` (a user-facing filter). No index on this column means full sequential scan on `audio_scans` for every filtered request. Add `index=True`.

---

### 🟡 MED-02 — `verdict` Column Has No Index on `AudioScan`
**File:** [`api/models/models.py:72`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/models/models.py#L72)

```python
verdict = Column(Enum(Verdict), nullable=False)
```
Also filtered in history queries. No index. Add `index=True`.

---

### 🟡 MED-03 — `scanned_at` Has No Index
**File:** [`api/models/models.py:75`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/models/models.py#L75)

The default sort order for all history endpoints is `ORDER BY scanned_at DESC`. Without an index this is a full-table sequential sort for every page load. Add an index (ideally a `BRIN` or `BTREE DESC` index since it's an append-only time column).

---

### 🟡 MED-04 — Offset Pagination (`/api/history`) Has O(N) Performance
**File:** [`api/main.py:135-140`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/main.py#L135-L140)

```python
.offset(offset)
```
PostgreSQL must scan and discard `offset` rows before returning results. At `offset=10000` the query is 500× slower than at `offset=0`. The cursor-based approach in `/api/scans/history` is better; the mobile `/api/history` compat endpoint should be migrated to cursor pagination too.

---

### 🟡 MED-05 — Cursor Pagination Has an Extra DB Lookup Per Page
**File:** [`api/repositories/scan_repository.py:51`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/repositories/scan_repository.py#L51-L56)

```python
cursor_scan = await self.session.get(AudioScan, cursor)  # extra round-trip
```
For every paginated page request, a full extra `SELECT * FROM audio_scans WHERE id = $1` is issued. This could be avoided by encoding `(scanned_at, id)` as the cursor value directly (e.g., base64-encoded JSON), eliminating the lookup.

---

### 🟡 MED-06 — `/api/stats` Has No Caching
**File:** [`api/main.py:170-200`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/main.py#L170-L200)

The aggregate stats query (5 `COUNT`/`SUM`/`AVG` operations on the full table) runs on every call. The `ModelTelemetry` component calls both `fetchStats()` and `fetchHistory(100)` on every mount. With no caching at API or client level, navigating to the Telemetry tab always triggers two uncached full-table aggregations.

---

## 3. ML Pipeline Performance

### 🟠 HIGH-08 — librosa in Streaming Loop Blocks Event Loop on Every Window
**File:** [`src/pipeline.py:207-210`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/src/pipeline.py#L207-L210)

```python
def _process_window(self, window: np.ndarray) -> WindowResult:
    _, mel_tensor, _ = preprocess_audio_array(window, ...)  # librosa — synchronous, CPU-bound
    prob_ai = run_inference(self.session, mel_tensor)        # ONNX — synchronous, CPU-bound
```
In the `/stream` WebSocket endpoint, `sp.write(chunk)` is called from the async handler. Each call to `_process_window` blocks the event loop for however long librosa + ONNX take (potentially 100–500ms per window). During that time no other WebSocket message can be received or sent. A dedicated worker thread/process is required.

---

### 🟠 HIGH-09 — `np.concatenate` in a Hot Path Creates New Arrays Every Chunk
**File:** [`src/pipeline.py:156`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/src/pipeline.py#L156)

```python
self._buffer = np.concatenate([self._buffer, chunk])
```
Called on every audio chunk (every ~256 ms at the 4096-sample buffer size). `np.concatenate` allocates a brand new array every call. Over a 30-second call this allocates ~120 intermediate arrays that must be GC'd. Use `collections.deque` or a pre-allocated ring buffer with `np.roll`, and track write position with a pointer.

Similarly:
```python
self._buffer = self._buffer[self.hop_samples:]   # line 164 — another allocation
```
This creates a new view/copy on every hop. Use `np.ndarray` with a circular index.

---

### 🟠 HIGH-10 — `_history = self._history[-self.history_size:]` — List Slice Every Window
**File:** [`src/risk_engine.py:130`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/src/risk_engine.py#L130)

```python
self._history = self._history[-self.history_size:]
```
Creates a new Python list every time the history overflows. Use `collections.deque(maxlen=history_size)` which is O(1) append/pop and bounded by design.

---

### 🟡 MED-07 — librosa Called Twice With Identical Parameters for Same Data
**File:** [`src/features.py:68-71`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/src/features.py#L68-L71), [`src/features.py:120-123`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/src/features.py#L120-L123)

`preprocess_audio` and `preprocess_audio_array` duplicate the identical mel spectrogram pipeline (stages 4–6). They share no code or cache. For the streaming path, every window recomputes from scratch with no memoization. This is unavoidable for different windows but should at least be a single shared function.

---

### 🟡 MED-08 — `ScriptProcessorNode` is Deprecated
**File:** [`frontend/src/hooks/useAudioStream.ts:107`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/hooks/useAudioStream.ts#L107)

```ts
const processor = audioCtx.createScriptProcessor(4096, 1, 1);
```
`ScriptProcessorNode` is deprecated in the Web Audio API spec and will be removed in future browsers. The replacement is `AudioWorkletNode`, which runs on a dedicated audio thread and does not block the main JS thread. The current implementation causes audio glitches under load and may stop working in Chrome Canary.

---

### 🟡 MED-09 — ONNX Runtime Runs Only on CPU
**File:** [`src/model.py:48`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/src/model.py#L48)

```python
sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
```
No GPU, DirectML, or CUDA provider is attempted. For a deployed service handling concurrent streams this severely limits throughput. `onnxruntime` can auto-detect and use available hardware accelerators if the providers list is ordered: `["CUDAExecutionProvider", "CPUExecutionProvider"]`.

---

## 4. Database & Query Inefficiencies

### 🟠 HIGH-11 — `spectral_features` JSONB Column Stores Derived/Redundant Data
**File:** [`api/main.py:82`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/main.py#L82)

```python
spectral_features={"confidence": float(confidence), "duration": float(duration_s)},
```
`confidence` is derivable from `impersonation_risk_score` + `verdict`. Storing it separately as JSONB creates:
1. Schema drift risk (JSONB has no type enforcement).
2. Inconsistent truth (what if they disagree?).
3. Wasted storage and indexing overhead on JSONB.

---

### 🟡 MED-10 — `get_trusted_contacts` Makes Two Queries When One Will Do
**File:** [`api/routes/users.py:64-67`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/routes/users.py#L64-L67)

```python
user = await repo.get_user_by_id(user_id)   # Query 1: check user exists
if not user: raise 404
contacts = await repo.get_trusted_contacts(user_id)  # Query 2: get contacts
```
Can be merged into a single LEFT JOIN query. If the user doesn't exist, the contacts query returns empty. This pattern is repeated throughout `users.py`.

---

### 🟡 MED-11 — `next_cursor` Is Always the Last Item ID, Even on Last Page
**File:** [`api/repositories/scan_repository.py:62`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/repositories/scan_repository.py#L62)

```python
next_cursor = scans[-1].id if scans else None
```
This sets `next_cursor` even when the current page has fewer items than `limit`, meaning the UI will show a "Load More" button that returns an empty next page. Should be `next_cursor = scans[-1].id if len(scans) == limit else None`.

---

## 5. WebSocket Streaming Issues

### 🔴 CRIT-06 — WebSocket Handler Has No Authentication or Origin Check
**File:** [`api/main.py:217-251`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/main.py#L217-L251)

The `/stream` WebSocket endpoint accepts connections from any origin. Unlike HTTP, WebSocket connections are not protected by CORS — any webpage can connect. This means anyone can:
- Stream audio to your inference server.
- Consume unlimited GPU/CPU resources.
- Connect thousands of persistent WebSocket sessions.

---

### 🟠 HIGH-12 — WebSocket Has No Message Size Limit
**File:** [`api/main.py:232`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/main.py#L232)

```python
data = await websocket.receive_bytes()
```
A client can send arbitrarily large binary messages. `np.frombuffer(data, dtype=np.float32)` will allocate a numpy array of the full size. A single 1 GB message would allocate multiple large arrays during processing.

---

### 🟠 HIGH-13 — WebSocket `flush()` Results Are Discarded Silently
**File:** [`api/main.py:248-250`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/main.py#L248-L250)

```python
except WebSocketDisconnect:
    results = sp.flush()
    for r in results:
        engine.ingest(r.prob_ai)  # ← result ingested but NEVER sent back
```
On disconnect, the flush results are computed (expensive CPU work) but the `await websocket.send_json(...)` is never called — they're just thrown away. The CPU work is wasted. Either skip the flush on disconnect, or persist the final assessment to the database.

---

### 🟡 MED-12 — Audio Leaks to `audioCtx.destination` (Speaker)
**File:** [`frontend/src/hooks/useAudioStream.ts:117-118`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/hooks/useAudioStream.ts#L117-L118)

```ts
source.connect(processor);
processor.connect(audioCtx.destination);  // ← feeds mic back to speakers
```
This feeds the microphone input back to the user's speakers, causing audio feedback (echo/howling). Should be `processor.connect(audioCtx.destination)` only if you intentionally want monitoring. Disconnect from destination and only connect to the processor for analysis.

---

### 🟡 MED-13 — No WebSocket Reconnect Logic
**File:** [`frontend/src/hooks/useAudioStream.ts:83-86`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/hooks/useAudioStream.ts#L83-L86)

```ts
wsRef.current.onclose = () => {
    stopStreamRef.current();  // ← gives up on any close
};
```
Any network hiccup (brief WiFi drop, server restart) permanently stops the stream with no retry. For a real-time voice security product, this needs exponential backoff reconnection with state preservation.

---

## 6. Frontend Performance & State

### 🔴 CRIT-07 — `streamingResult` Is Recomputed With an IIFE on Every Render
**File:** [`frontend/src/components/LiveDetector.tsx:305-326`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/components/LiveDetector.tsx#L305-L326)

```tsx
const streamingResult: DetectionResult | null = latestResult
  ? (() => {   // ← IIFE runs every render
      let mappedVerdict = ...;
      return { score: ..., details: { ... } };
    })()
  : null;
```
This large transformation runs on *every single render* — which happens on every WebSocket message (potentially multiple times per second). It should be `useMemo(() => ..., [latestResult])`.

---

### 🟠 HIGH-14 — `TrustedCirclePanel` Fetches `GET /api/users/?limit=1` Then a Second Call Unconditionally
**File:** [`frontend/src/components/LiveDetector.tsx:164-170`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/components/LiveDetector.tsx#L164-L170)

```tsx
const usersRes = await fetch(`${API_BASE}/api/users/?limit=1`);  // Fetch 1
...
const contactsRes = await fetch(`${API_BASE}/api/users/${users[0].id}/contacts`);  // Fetch 2
```
Two sequential fetches every time the panel is opened. No caching, no SWR, no `useQuery`. If the panel is opened multiple times in a session, this fires each time.

---

### 🟠 HIGH-15 — `ModelTelemetry` Fetches 100 History Entries for Client-Side Charting
**File:** [`frontend/src/components/ModelTelemetry.tsx:168`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/components/ModelTelemetry.tsx#L168)

```ts
const [s, h] = await Promise.all([fetchStats(), fetchHistory(100)]);
```
The full 100-entry history payload is transferred just to build a client-side histogram and a 30-point trend line. The histogram should be computed server-side (or at least cached). The trend chart only uses `slice(-30)` of those 100 items — only 30 were needed.

---

### 🟠 HIGH-16 — `AuditLogs` Computes Language Filter List from Client Data, Not Server
**File:** [`frontend/src/components/AuditLogs.tsx:155`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/components/AuditLogs.tsx#L155)

```tsx
const languages = ["all", ...Array.from(new Set(items.map(i => i.language).filter(Boolean)))];
```
The language dropdown is derived from the currently loaded 20-item page. If a language only appears on page 3, it won't be in the filter dropdown. The server should expose a `/api/languages` distinct values endpoint.

---

### 🟡 MED-14 — `MetricRow` Bars Animate from 0 on Every Streaming Result Update
**File:** [`frontend/src/components/LiveDetector.tsx:505-510`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/components/LiveDetector.tsx#L505-L510)

```tsx
<motion.div
  initial={{ width: 0 }}
  animate={{ width: `${value}%` }}
  transition={{ duration: 1, ease: "easeOut" }}
/>
```
`initial={{ width: 0 }}` resets to zero on every component re-render caused by a new WebSocket result. Since `streamingResult` changes on every window, all four bars slide from 0 multiple times per second. Use `layout` prop or track previous value to animate from current to new value.

---

### 🟡 MED-15 — No `React.memo` / `useCallback` on `AuditLogs` Row Renders
**File:** [`frontend/src/components/AuditLogs.tsx:265-301`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/components/AuditLogs.tsx#L265-L301)

All 20 rows re-render on every filter change or state update. Since `VerdictBadge` is a pure function, it should be `React.memo`'d. The inline `motion.tr` with complex class computations should be extracted to a memoized `AuditRow` component.

---

### 🟡 MED-16 — `buildMockHistory()` Creates New Array With `Math.random()` on Every Render in Non-Production
**File:** [`frontend/src/components/ModelTelemetry.tsx:41-51`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/components/ModelTelemetry.tsx#L41-L51)

```ts
function buildMockHistory(): HistoryEntry[] {
  return Array.from({ length: 60 }, (_, i) => ({
    probability: i % 3 === 0 ? 0.6 + Math.random() * 0.38 : Math.random() * 0.35,  // ← impure
  }));
}
```
`Math.random()` in mock data construction called at error-fallback time means the chart jitters on every re-render in fallback mode. Move mock data to a module-level constant.

---

## 7. Bundle Size & Dependencies

### 🟡 MED-17 — Recharts Is Loaded on Every Page (Including Non-Telemetry)
**File:** [`frontend/src/components/ModelTelemetry.tsx:1-19`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/components/ModelTelemetry.tsx#L1-L19)

`recharts` adds ~170 KB gzipped. It should only be loaded when the Telemetry tab is active. Use:
```tsx
const ModelTelemetry = dynamic(() => import("@/components/ModelTelemetry"), { ssr: false });
```
Same applies to `framer-motion` (already large) — it's used in every component. Consider using CSS animations for simple effects and reserving Framer only for complex orchestrations.

---

### 🟡 MED-18 — `lucide-react` at v1.48.0 May Not Support Tree-Shaking Properly
**File:** [`frontend/package.json:14`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/package.json#L14)

Both `lucide-react` and `recharts` import many symbols. Verify that the build output tree-shakes unused icons. `LiveDetector.tsx` imports 9 icons; `ModelTelemetry.tsx` imports 6. Bundler analysis (e.g., `@next/bundle-analyzer`) should be run.

---

### 🟢 LOW-01 — `clsx` and `tailwind-merge` Are Both Installed But `cn()` Utility Is Only 2 Lines
**File:** [`frontend/src/lib/utils.ts`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/lib/utils.ts)

Low issue, but `clsx` is only used through the `cn()` wrapper. If TailwindMerge's `twMerge` isn't being used for conflict resolution, just `clsx` alone saves a dependency.

---

## 8. Reliability & Error Handling

### 🔴 CRIT-08 — `preprocess_audio` Raises Uncaught `ValueError` Inside Async Route
**File:** [`api/main.py:63`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/main.py#L63)

```python
mel_norm, mel_tensor, duration_s = preprocess_audio(audio_bytes, ext)
# ↑ raises ValueError if too short, RuntimeError if corrupt
```
No try/except wraps the preprocessing call. If a user uploads a 0.1s clip or a corrupted file, FastAPI gets an unhandled exception that returns a raw 500 with a Python traceback — which leaks internal server paths and library versions.

---

### 🟠 HIGH-17 — WebSocket Handler Catches Only `WebSocketDisconnect`
**File:** [`api/main.py:247`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/main.py#L247)

```python
except WebSocketDisconnect:
    ...
```
Any other exception in the loop (numpy error, ONNX runtime crash, corrupt PCM frame) will propagate unhandled, crash the coroutine silently, and leave the WebSocket in an indeterminate state without sending an error message to the client. Add a broad `except Exception as e` with structured logging.

---

### 🟠 HIGH-18 — `handleFileUpload` Has No try/catch
**File:** [`frontend/src/components/LiveDetector.tsx:339-348`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/components/LiveDetector.tsx#L339-L348)

```tsx
const handleFileUpload = async (e) => {
    ...
    const res = await analyzeAudio(e.target.files[0], language);  // ← can throw
    setResult(res);
    setIsAnalyzingFile(false);  // ← never reached on error
};
```
If `analyzeAudio` throws, `setIsAnalyzingFile(false)` is never called, leaving the UI permanently in a loading/analyzing state. Wrap in try/catch/finally.

---

### 🟠 HIGH-19 — `model_error` Leaks Internal Filesystem Paths to API Clients
**File:** [`api/main.py:211`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/main.py#L211)

```python
"model_error": _model_error,
```
`_model_error` may contain strings like `"Model file not found: /home/user/vaniguard/models/vaniguard.onnx"`. This exposes the server's filesystem layout to any caller.

---

### 🟡 MED-19 — No `AbortController` / Request Cancellation in API Client
**File:** [`frontend/src/lib/api.ts:52-55`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/lib/api.ts#L52-L55)

If the user uploads a file, then immediately navigates away, the `fetch` request continues in the background, state updates may fire on an unmounted component, and the server wastes inference CPU. Use `AbortController` and cancel inflight requests on component unmount.

---

### 🟡 MED-20 — `exportCsv` Injects Unsanitized Data Into CSV
**File:** [`frontend/src/components/AuditLogs.tsx:71-72`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/components/AuditLogs.tsx#L71-L72)

```ts
const rows = items.map(i => `${i.id},${i.time},${i.language},${i.risk},${i.verdict},${i.action}`);
```
CSV injection: if `i.language` contains a comma, newline, or formula prefix (`=CMD|...`), the exported CSV is malformed or exploitable in Excel. Each field should be wrapped in quotes and have internal quotes escaped.

---

## 9. Scalability Issues

### 🟠 HIGH-20 — Model Loaded at Module Import Time (Blocks Server Start)
**File:** [`api/main.py:47`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/main.py#L47)

```python
session, _model_error = load_model()   # ← called at import time
```
This blocks the entire FastAPI startup until the ONNX model file is read from disk (potentially 50-200ms, longer on cold starts). Should use a `@app.on_event("startup")` lifespan handler instead, which allows the server to bind to the port and respond to health checks while the model loads.

---

### 🟠 HIGH-21 — Single `StreamPipeline` + `RiskEngine` Instance Per WebSocket Connection
**File:** [`api/main.py:226-227`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/main.py#L226-L227)

```python
sp = StreamPipeline(session=session)
engine = RiskEngine()
```
These are created per connection, which is correct in principle, but the `session` (ONNX session) is shared globally. `ort.InferenceSession.run()` is documented as thread-safe, but under concurrent WebSocket connections all inference calls serialize on the single session. For scale: use a session pool or per-connection sessions.

---

### 🟡 MED-21 — `pool_size=10, max_overflow=20` Is Untuned
**File:** [`api/core/database.py:17-19`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/api/core/database.py#L17-L19)

30 total connections are opened immediately regardless of load. Under light load this wastes PostgreSQL memory. Under inference-heavy load, the ONNX CPU work (not DB queries) is the bottleneck anyway. This should be profiled and tuned; consider `pool_timeout`, `pool_recycle`.

---

## 10. Accessibility (A11y)

### 🟠 HIGH-22 — Interactive Buttons Have No Accessible Labels
**Files:** Multiple components

```tsx
<button onClick={onClose} className="text-slate-500 ...">
    <X className="w-5 h-5" />  {/* ← no aria-label */}
</button>
```
Icon-only buttons (close, refresh, resend) have no `aria-label`. Screen readers announce "button" with no context. All icon buttons need `aria-label="Close"`, `aria-label="Refresh data"`, etc.

---

### 🟠 HIGH-23 — Color-Coded Risk Communication Without Text Alternative
**File:** [`frontend/src/components/AuditLogs.tsx:283-293`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/components/AuditLogs.tsx#L283-L293)

```tsx
<span className={`font-mono font-bold ${item.risk > 70 ? "text-rose-400" : ...}`}>
    {item.risk}%
</span>
```
Risk severity is communicated by color only. For users with color blindness (8% of males), red/green are indistinguishable. Add `aria-label="High risk: 94%"` or a text indicator alongside color.

---

### 🟠 HIGH-24 — `<html lang="en">` But Content Targets Hindi/Telugu/Tamil Users
**File:** [`frontend/src/app/layout.tsx:57`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/app/layout.tsx#L57)

The application is explicitly for Indian language users. `lang="en"` means screen readers will pronounce any Hindi/Devanagari text in English phonetics. Pages or sections with non-Latin content need correct `lang` attributes.

---

### 🟡 MED-22 — Filter `<select>` Elements Have No `<label>` Tags
**File:** [`frontend/src/components/AuditLogs.tsx:172-197`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/components/AuditLogs.tsx#L172-L197)

The verdict and language dropdowns lack `<label>` elements. They have `id` attributes but no corresponding `<label for="...">`. Screen readers cannot identify these controls.

---

### 🟡 MED-23 — `RiskGauge` SVG Has No ARIA Role or Description
**File:** [`frontend/src/components/RiskGauge.tsx`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/components/RiskGauge.tsx)

The SVG gauge communicates the most critical information in the UI (risk score + verdict) but is invisible to screen readers. Add `role="img"` and `aria-label="Risk score: 87%, verdict: CLONED"`.

---

### 🟡 MED-24 — OTP Digits Rendered as Decorative `<div>` Elements
**File:** [`frontend/src/components/LiveDetector.tsx:93-100`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/components/LiveDetector.tsx#L93-L100)

```tsx
{otp.split("").map((digit, i) => (
    <motion.div key={i} ...>{digit}</motion.div>
))}
```
The 6-digit OTP is split into individual `<div>` elements. Screen readers will read "1 2 3 4 5 6" one by one. Wrap in a single `<span aria-label={`OTP code: ${otp}`}>` and make the individual tiles `aria-hidden`.

---

### 🟢 LOW-02 — No `prefers-reduced-motion` Check
All Framer Motion animations play unconditionally. Users who have OS-level reduced motion enabled still see all animations. Use `useReducedMotion()` from `framer-motion` to disable or simplify animations.

---

## 11. Concurrency & Race Conditions

### 🟠 HIGH-25 — Filter Change in `AuditLogs` Can Produce Stale State
**File:** [`frontend/src/components/AuditLogs.tsx:110-143`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/components/AuditLogs.tsx#L110-L143)

`fetchPage` is an async function triggered by filter changes via `useEffect`. If the user changes the verdict filter, then quickly changes the language filter, two concurrent fetches race. The first to resolve sets `items`, the second overwrites it — potentially displaying data for the wrong filter combination. Use a request-cancel token (AbortController) or a `useRef` sequence number to discard stale responses.

---

### 🟠 HIGH-26 — `stopStream` Called Inside WebSocket `onclose` Creates a Re-entrant Loop
**File:** [`frontend/src/hooks/useAudioStream.ts:83-86`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/hooks/useAudioStream.ts#L83-L86)

```ts
wsRef.current.onclose = () => {
    stopStreamRef.current();  // ← calls stopStream which calls ws.close() again
};
```
`stopStream` closes the WebSocket (`wsRef.current.close()`). If `onclose` calls `stopStream`, and `stopStream` tries to close the already-closing WebSocket, it could trigger `onclose` again. Guard with a `isClosing` ref.

---

### 🟡 MED-25 — No Debounce on Microphone Permission Re-request
**File:** [`frontend/src/hooks/useAudioStream.ts:89-95`](file:///c:/Users/Asus/OneDrive/Desktop/Vani%20Guard/frontend/src/hooks/useAudioStream.ts#L89-L95)

If the user rapidly clicks "Start / Stop Live Stream", `getUserMedia()` can be called multiple times before the previous call resolves. This leaks `MediaStream` objects and holds multiple mic tracks open simultaneously.

---

## 12. Priority Summary Table

| ID | Severity | Category | Issue |
|----|----------|----------|-------|
| CRIT-01 | 🔴 Critical | Security | Wildcard CORS + credentials |
| CRIT-02 | 🔴 Critical | Security | Hardcoded DB password in source |
| CRIT-03 | 🔴 Critical | Security | No authentication on any endpoint |
| CRIT-04 | 🔴 Critical | Performance | Synchronous ONNX in async handler blocks event loop |
| CRIT-05 | 🔴 Critical | Performance | Full file read into RAM, no size limit |
| CRIT-06 | 🔴 Critical | Security | WebSocket has no auth or origin validation |
| CRIT-07 | 🔴 Critical | Performance | IIFE recomputed on every render during live stream |
| CRIT-08 | 🔴 Critical | Reliability | Unhandled ValueError/RuntimeError in async route |
| HIGH-01 | 🟠 High | Security | No file type or size validation |
| HIGH-02 | 🟠 High | Security | Hardcoded localhost URLs in 4 files |
| HIGH-03 | 🟠 High | Security | OTP is client-side only (security theater) |
| HIGH-04 | 🟠 High | Security | Plaintext WebSocket `ws://` (no TLS) |
| HIGH-05 | 🟠 High | Performance | Double commit per /analyze request |
| HIGH-06 | 🟠 High | Database | Sequential count query + data query |
| HIGH-07 | 🟠 High | Database | No index on `language` column |
| HIGH-08 | 🟠 High | Performance | librosa blocks async event loop in WebSocket stream |
| HIGH-09 | 🟠 High | Performance | np.concatenate allocates new array on every chunk |
| HIGH-10 | 🟠 High | Performance | List slice in hot path (use deque) |
| HIGH-12 | 🟠 High | Security | No WebSocket message size limit |
| HIGH-13 | 🟠 High | Reliability | flush() results discarded on disconnect |
| HIGH-14 | 🟠 High | Performance | TrustedCircle makes 2 sequential API calls |
| HIGH-15 | 🟠 High | Performance | Fetches 100 history rows for a 30-point chart |
| HIGH-17 | 🟠 High | Reliability | WebSocket catches only disconnect, not all errors |
| HIGH-18 | 🟠 High | Reliability | handleFileUpload has no try/catch/finally |
| HIGH-19 | 🟠 High | Security | Internal server path exposed in health endpoint |
| HIGH-20 | 🟠 High | Scalability | Model loaded at import time (blocks startup) |
| HIGH-22 | 🟠 High | A11y | Icon buttons have no aria-label |
| HIGH-23 | 🟠 High | A11y | Color-only risk communication |
| HIGH-25 | 🟠 High | Race Condition | Filter changes race in AuditLogs |
| HIGH-26 | 🟠 High | Race Condition | onclose → stopStream re-entrant loop |
| MED-01 | 🟡 Medium | Security | No rate limiting on /analyze |
| MED-07 | 🟡 Medium | Performance | librosa pipeline duplicated in two functions |
| MED-08 | 🟡 Medium | Performance | ScriptProcessorNode is deprecated |
| MED-11 | 🟡 Medium | Bug | next_cursor set even on last page |
| MED-12 | 🟡 Medium | Bug | Mic audio leaks to speakers (feedback) |
| MED-14 | 🟡 Medium | Performance | Metric bars animate from 0 on every update |
| MED-20 | 🟡 Medium | Security | CSV injection in audit export |
| MED-21 | 🟡 Medium | Scalability | Untuned DB connection pool |
| MED-22 | 🟡 Medium | A11y | Filter selects have no label |
| MED-23 | 🟡 Medium | A11y | RiskGauge SVG not accessible |
| MED-25 | 🟡 Medium | Race Condition | Multiple getUserMedia on rapid toggle |

---

> **Recommended immediate priorities:**
> 1. CRIT-04 (event loop blocking) — impacts every user under load
> 2. CRIT-03 (no auth) — full data exposure
> 3. CRIT-01+CRIT-02 (CORS/credentials) — basic hardening
> 4. HIGH-09+HIGH-10 (numpy alloc in hot path) — streaming latency
> 5. CRIT-07 (IIFE in render) — UI freezes during live stream
