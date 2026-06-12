import { useCallback, useEffect, useRef, useState } from "react";
import { askKnowledge, clearKnowledge, deleteKnowledgeDocument, exportKnowledge, getDocumentContent, importKnowledge, importKnowledgeDocument, importKnowledgeDocumentFromPath, listKnowledgeDocuments, searchKnowledge } from "../api";
import type { DocumentContent, KnowledgeAnswer, KnowledgeChunk, KnowledgeDocument } from "../types";

interface KnowledgePanelProps {
  onClose: () => void;
}

export function KnowledgePanel({ onClose }: KnowledgePanelProps) {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [askQuery, setAskQuery] = useState("");
  const [searchResults, setSearchResults] = useState<KnowledgeChunk[]>([]);
  const [answer, setAnswer] = useState<KnowledgeAnswer | null>(null);
  const [searching, setSearching] = useState(false);
  const [asking, setAsking] = useState(false);
  const [importing, setImporting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [previewDoc, setPreviewDoc] = useState<DocumentContent | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const importFileInputRef = useRef<HTMLInputElement>(null);

  const hasNativePicker = Boolean(window.keobotDesktop?.chooseKnowledgeFiles);

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    try {
      const docs = await listKnowledgeDocuments();
      setDocuments(docs);
    } catch {
      setStatus("Không thể tải danh sách tài liệu.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  const importSingleFile = async (path: string, name: string) => {
    try {
      const result = await importKnowledgeDocumentFromPath(path);
      if (result.ok) {
        setStatus(`Đã import: ${result.filename as string} (${result.chunk_count as number} chunks)`);
      } else {
        setStatus(`Lỗi: ${result.error as string}`);
      }
    } catch {
      setStatus(`Lỗi khi import ${name}.`);
    }
  };

  const handleNativePick = async () => {
    const picker = window.keobotDesktop?.chooseKnowledgeFiles;
    if (!picker) return;
    setImporting(true);
    setStatus("Đang chọn file...");
    try {
      const result = await picker();
      if (result.canceled || result.files.length === 0) {
        setStatus("");
        return;
      }
      setStatus(`Đang import ${result.files.length} file(s)...`);
      for (const file of result.files) {
        await importSingleFile(file.path, file.name);
      }
      void loadDocuments();
    } catch {
      setStatus("Lỗi khi chọn file.");
    } finally {
      setImporting(false);
    }
  };

  const handleBrowseImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setImporting(true);
    setStatus("Đang import...");
    for (const file of Array.from(files)) {
      try {
        const result = await importKnowledgeDocument(file);
        if (result.ok) {
          setStatus(`Đã import: ${result.filename as string} (${result.chunk_count as number} chunks)`);
        } else {
          setStatus(`Lỗi: ${result.error as string}`);
        }
      } catch {
        setStatus(`Lỗi khi import ${file.name}.`);
      }
    }
    void loadDocuments();
    if (fileInputRef.current) fileInputRef.current.value = "";
    setImporting(false);
  };

  const handleDelete = async (docId: number, name: string) => {
    if (!confirm(`Xóa tài liệu "${name}"?`)) return;
    try {
      await deleteKnowledgeDocument(docId);
      setStatus(`Đã xóa: ${name}`);
      void loadDocuments();
    } catch {
      setStatus(`Lỗi khi xóa ${name}.`);
    }
  };

  const handlePreview = async (docId: number) => {
    try {
      const content = await getDocumentContent(docId);
      setPreviewDoc(content);
    } catch {
      setStatus("Lỗi khi tải nội dung tài liệu.");
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const result = await searchKnowledge(searchQuery);
      setSearchResults(result.results);
    } catch {
      setStatus("Lỗi tìm kiếm.");
    } finally {
      setSearching(false);
    }
  };

  const handleAsk = async () => {
    if (!askQuery.trim()) return;
    setAsking(true);
    setAnswer(null);
    try {
      const result = await askKnowledge(askQuery);
      setAnswer(result);
    } catch {
      setStatus("Lỗi khi hỏi tài liệu.");
    } finally {
      setAsking(false);
    }
  };

  const handleClearAll = async () => {
    if (!confirm("Xóa tất cả tài liệu và index? Hành động này không thể hoàn tác.")) return;
    try {
      const result = await clearKnowledge(true);
      if (result.ok) {
        setStatus(`Đã xóa ${result.documents_deleted} tài liệu.`);
        void loadDocuments();
      } else {
        setStatus(result.error ?? "Lỗi khi xóa.");
      }
    } catch {
      setStatus("Lỗi khi xóa tất cả tài liệu.");
    }
  };

  const handleExport = async () => {
    setExporting(true);
    setStatus("Đang xuất dữ liệu...");
    try {
      const result = await exportKnowledge();
      const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const timestamp = new Date().toISOString().slice(0, 10);
      a.download = `keobot-knowledge-backup-${timestamp}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setStatus(`Đã xuất ${result.records.length} tài liệu.`);
    } catch {
      setStatus("Lỗi khi xuất dữ liệu.");
    } finally {
      setExporting(false);
    }
  };

  const handleImportBackup = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setStatus("Đang nhập dữ liệu...");
    try {
      const text = await file.text();
      const data = JSON.parse(text) as { records: Array<{ document: KnowledgeDocument; chunks: KnowledgeChunk[] }> };
      const result = await importKnowledge({ records: data.records, mode: "merge" });
      setStatus(`Đã nhập: ${result.documents_imported} tài liệu, ${result.chunks_imported} chunks.`);
      if (result.errors.length > 0) {
        setStatus(prev => `${prev} Lỗi: ${result.errors[0]}`);
      }
      void loadDocuments();
    } catch {
      setStatus("Lỗi khi nhập dữ liệu. Định dạng file không hợp lệ.");
    } finally {
      setImporting(false);
      if (importFileInputRef.current) importFileInputRef.current.value = "";
    }
  };

  const formatSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (dateStr: string): string => {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString("vi-VN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  };

  return (
    <section className="panel knowledge-panel">
      <div className="panel-inner">
        <div className="panel-title">
          <div>
            <p className="section-kicker">Local Knowledge</p>
            <h2>Tài liệu</h2>
          </div>
          <button className="action-button secondary" type="button" onClick={onClose}>
            Đóng
          </button>
        </div>

        <div className="settings-fields">
          <div className="settings-field">
            <span>Import file</span>
            {hasNativePicker ? (
              <button className="action-button secondary" type="button" onClick={handleNativePick} disabled={importing}>
                {importing ? "Đang import..." : "Choose files"}
              </button>
            ) : (
              <>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".txt,.md,.pdf,.docx"
                  multiple
                  onChange={handleBrowseImport}
                  style={{ display: "none" }}
                />
                <button className="action-button secondary" type="button" onClick={() => fileInputRef.current?.click()}>
                  Chọn file
                </button>
              </>
            )}
          </div>
          <div className="settings-field" style={{ flexDirection: "row", gap: "8px" }}>
            <button className="action-button secondary" type="button" onClick={handleExport} disabled={exporting || documents.length === 0}>
              {exporting ? "Đang xuất..." : "Sao lưu dữ liệu"}
            </button>
            <input
              ref={importFileInputRef}
              type="file"
              accept=".json"
              onChange={handleImportBackup}
              style={{ display: "none" }}
            />
            <button className="action-button secondary" type="button" onClick={() => importFileInputRef.current?.click()} disabled={importing}>
              Khôi phục từ sao lưu
            </button>
          </div>
        </div>

        <div className="settings-group">
          <h3>Danh sách tài liệu ({documents.length})</h3>
          {loading ? (
            <p className="muted-copy">Đang tải...</p>
          ) : documents.length === 0 ? (
            <p className="muted-copy">Chưa có tài liệu nào.</p>
          ) : (
            <div className="knowledge-doc-list">
              {documents.map((doc) => (
                <div key={doc.id} className="knowledge-doc-row">
                  <div className="knowledge-doc-info">
                    <strong>{doc.original_filename}</strong>
                    <span className="muted-copy">
                      {doc.file_type.toUpperCase()} · {formatSize(doc.size_bytes)} · {doc.chunk_count} chunks · {formatDate(doc.created_at)}
                    </span>
                    {doc.status === "failed" && <span className="status-error">Failed: {doc.error_message}</span>}
                    {doc.status === "indexed" && <span className="status-ok">Indexed</span>}
                  </div>
                  <div className="knowledge-doc-actions" style={{ display: "flex", gap: "4px", alignItems: "center" }}>
                    <button className="action-button secondary" type="button" onClick={() => handlePreview(doc.id)}>
                      Xem
                    </button>
                    <button className="action-button secondary danger" type="button" onClick={() => handleDelete(doc.id, doc.original_filename)}>
                      Xóa
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
          {documents.length > 0 && (
            <div style={{ marginTop: "0.5rem" }}>
              <button className="action-button secondary danger" type="button" onClick={handleClearAll}>
                Xóa tất cả
              </button>
            </div>
          )}
        </div>

        {previewDoc && (
          <div className="settings-group">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
              <h3 style={{ margin: 0 }}>Xem trước: {previewDoc.original_filename}</h3>
              <button className="action-button secondary" type="button" onClick={() => setPreviewDoc(null)}>
                Đóng
              </button>
            </div>
            <div className="knowledge-preview-content" style={{ maxHeight: "400px", overflowY: "auto", padding: "12px", background: "var(--bg)", borderRadius: "8px", fontSize: "0.9rem", lineHeight: "1.6", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
              {previewDoc.content}
            </div>
          </div>
        )}

        <div className="settings-group">
          <h3>Tìm kiếm trong tài liệu</h3>
          <div className="settings-field">
            <div className="settings-field" style={{ display: "flex", gap: "8px", flexDirection: "row" }}>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") void handleSearch(); }}
                placeholder="Nhập từ khóa..."
                style={{ flex: 1 }}
              />
              <button className="action-button secondary" type="button" onClick={handleSearch} disabled={searching}>
                {searching ? "Đang tìm..." : "Tìm"}
              </button>
            </div>
            <span className="muted-copy" style={{ fontSize: "0.8rem" }}>
              Tìm kiếm kết hợp: từ khóa + ngữ nghĩa
            </span>
          </div>
          {searchResults.length > 0 && (
            <div className="knowledge-search-results">
              {searchResults.map((chunk) => (
                <div key={chunk.id} className="knowledge-chunk">
                  <div className="knowledge-chunk-header">
                    <strong>{chunk.source_title || `Chunk ${chunk.chunk_index}`}</strong>
                    {chunk.source_location && <span className="muted-copy">{chunk.source_location}</span>}
                  </div>
                  <p className="knowledge-chunk-text">{chunk.text.slice(0, 500)}{chunk.text.length > 500 ? "..." : ""}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="settings-group">
          <h3>Hỏi tài liệu</h3>
          <p className="muted-copy">Đặt câu hỏi dựa trên nội dung tài liệu đã import.</p>
          <div className="settings-field">
            <div className="settings-field" style={{ display: "flex", gap: "8px", flexDirection: "row" }}>
              <input
                type="text"
                value={askQuery}
                onChange={(e) => setAskQuery(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") void handleAsk(); }}
                placeholder="Ví dụ: CV của tôi có gì?"
                style={{ flex: 1 }}
              />
              <button className="action-button secondary" type="button" onClick={handleAsk} disabled={asking}>
                {asking ? "Đang hỏi..." : "Hỏi"}
              </button>
            </div>
            <span className="muted-copy" style={{ fontSize: "0.8rem" }}>
              Trả lời bằng hybrid search (từ khóa + ngữ nghĩa) kèm trích dẫn nguồn
            </span>
          </div>
          {answer && (
            <div className="knowledge-answer">
              <p className="knowledge-answer-text">{answer.answer}</p>
              {answer.sources.length > 0 && (
                <details>
                  <summary>Nguồn ({answer.sources.length})</summary>
                  {answer.sources.map((source, idx) => (
                    <div key={`${source.document_id}-${source.chunk_index}`} className="knowledge-source">
                      <strong>[{idx + 1}] {source.source_title}</strong>
                      <p className="muted-copy">{source.text.slice(0, 300)}...</p>
                    </div>
                  ))}
                </details>
              )}
            </div>
          )}
        </div>

        <p className="settings-status">{status}</p>
      </div>
    </section>
  );
}
