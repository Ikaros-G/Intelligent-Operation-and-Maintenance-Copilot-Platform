# Multi-file Knowledge Base Upload Design

## Goal

Allow a user to select up to 10 TXT or Markdown files in one file-picker action. Process the files sequentially and show an independent indexing result for every file.

The chat interface defaults to streaming mode on initial load and after creating a new conversation. Quick mode remains available in the mode menu.

## Interaction

- The existing file picker accepts multiple files.
- Each file keeps the current 50 MB per-file limit and supported extensions: `.txt`, `.md`, and `.markdown`.
- More than 10 selected files are rejected before upload with a clear notification.
- Invalid files are reported and skipped; valid files continue.
- For each valid file, the chat shows an indexing message followed by either:
  - `<filename> 文件成功上传到知识库`
  - `<filename> 知识库索引失败：<reason>`
- Files are processed sequentially so DashScope and Milvus are not flooded with concurrent indexing requests.

## Frontend Flow

1. Convert `FileList` to an array.
2. Validate selection count, extension, and per-file size.
3. Lock the upload control once for the complete batch.
4. For each valid file:
   - POST it to `/api/upload` using the existing single-file API.
   - Resolve the returned task status URL.
   - Poll until `SUCCESS`, `FAILURE`, or timeout.
   - Show that file's result and continue to the next file.
5. Clear the file input and unlock the UI after the batch completes.

The backend API remains unchanged because it already creates one isolated Celery task per uploaded file.

## Error Handling

- A network or indexing failure affects only the current file.
- The next valid file is still processed.
- A polling timeout is shown as still processing; the batch then continues.
- Unsupported or oversized files never reach the backend.

## Testing

- Verify the file input contains the `multiple` attribute.
- Verify selection validation enforces the 10-file and 50 MB limits.
- Verify sequential processing preserves input order and continues after one handler failure.
- Run JavaScript syntax checks and the existing upload response regression tests.
- Verify the served static files contain the multi-file implementation.
