import { useRef, useState } from 'react';
import { importRecords } from '../services/api';

function csvCell(value) {
  const text = String(value ?? '');
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function readImportError(error) {
  if (!error.response) return 'The backend is not reachable at http://localhost:8000. Start the FastAPI backend, then refresh this page.';
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail?.errors?.length) return `${detail.message || 'Import rejected.'} ${detail.errors.slice(0, 3).join(' · ')}`;
  return 'Import failed. Check the column headings and values, then try again.';
}

export default function DataImportPanel({ entity, headings, sampleRow, onImported }) {
  const fileInput = useRef(null);
  const [state, setState] = useState({ kind: '', message: '' });
  const [uploading, setUploading] = useState(false);

  const downloadTemplate = () => {
    const csv = [headings, sampleRow].map(row => row.map(csvCell).join(',')).join('\n');
    const file = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(file);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${entity}-import-template.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const upload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setUploading(true);
    setState({ kind: '', message: '' });
    try {
      const result = await importRecords(entity, file);
      await onImported?.();
      setState({ kind: 'success', message: result.data.message });
    } catch (error) {
      setState({ kind: 'error', message: readImportError(error) });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="import-panel">
      <input ref={fileInput} className="sr-only" type="file" accept=".csv,.xlsx" onChange={upload} />
      <div className="import-actions">
        <button type="button" className="btn btn-secondary" onClick={downloadTemplate}>Download CSV template</button>
        <button type="button" className="btn btn-primary" disabled={uploading} onClick={() => fileInput.current?.click()}>
          {uploading ? 'Importing…' : 'Import CSV / Excel'}
        </button>
      </div>
      <p className="import-note">.csv or .xlsx · existing matching records are updated</p>
      {state.message && <div className={`import-status ${state.kind === 'success' ? 'success' : 'error'}`}>{state.message}</div>}
    </div>
  );
}
