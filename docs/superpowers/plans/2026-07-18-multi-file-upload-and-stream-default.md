# Multi-file Upload And Stream Default Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Support sequential multi-file knowledge uploads and make streaming chat the default mode.

**Architecture:** Add a small browser-independent upload batch helper for validation and sequential execution. Keep the existing `/api/upload` endpoint and task polling contract; update `app.js` to coordinate the batch and update `index.html` for multi-select and streaming defaults.

**Tech Stack:** Vanilla JavaScript, HTML, Node.js assertion tests, FastAPI static serving.

## Global Constraints

- Accept at most 10 files per selection.
- Accept `.txt`, `.md`, and `.markdown`, with a 50 MB limit per file.
- Process accepted files sequentially and continue after one failure.
- Default to streaming chat on load and after creating a new conversation.

---

### Task 1: Upload Batch Helper

**Files:**
- Create: `static/uploadBatch.js`
- Create: `tests/frontend_upload_batch.test.js`

**Interfaces:**
- Produces: `validateSelection(files, options)` and `runSequentially(items, handler)`.

- [ ] Write assertions for count, extension, size, input order, and continuation after failure.
- [ ] Run `node tests/frontend_upload_batch.test.js` and confirm it fails because the helper is missing.
- [ ] Implement the UMD helper with `maxFiles=10` and `maxSize=50*1024*1024` defaults.
- [ ] Run the test and confirm it passes.

### Task 2: Multi-file UI Integration

**Files:**
- Modify: `static/index.html`
- Modify: `static/app.js`
- Test: `tests/frontend_upload_batch.test.js`

**Interfaces:**
- Consumes: `window.UploadBatch.validateSelection` and `window.UploadBatch.runSequentially`.
- Produces: `uploadFiles(files)` and an awaited `pollUploadTask(fileName, statusUrl)` result.

- [ ] Assert that `fileInput` contains `multiple` and `index.html` loads `uploadBatch.js` before `app.js`.
- [ ] Run the test and confirm those assertions fail.
- [ ] Change selection handling to validate all files, skip invalid files, and process accepted files sequentially.
- [ ] Await each task's terminal state before starting the next file.
- [ ] Run upload tests and JavaScript syntax checks.

### Task 3: Streaming Chat Default

**Files:**
- Modify: `static/index.html`
- Modify: `static/app.js`
- Create: `tests/frontend_default_mode.test.js`

**Interfaces:**
- Produces: `currentMode='stream'` on construction and new chat reset.

- [ ] Assert that JavaScript and initial HTML both select streaming mode.
- [ ] Run the test and confirm it fails against the current quick defaults.
- [ ] Change constructor, new-chat reset, label, and active dropdown item to streaming.
- [ ] Run the mode test and syntax checks.

### Task 4: Runtime Verification

**Files:**
- Sync: `static/index.html`, `static/app.js`, `static/uploadBatch.js`

- [ ] Copy changed static files into `aiops-api` because the current source directory is not mounted.
- [ ] Verify HTTP-served HTML includes `multiple`, `uploadBatch.js`, and the streaming selection.
- [ ] Submit two real files in sequence through the existing API and confirm both task states are `SUCCESS`.

