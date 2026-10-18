import { useState, useEffect } from 'react';
import { getSections, createSection, updateSection, deleteSection } from '../services/api';
import CrudTable from '../components/CrudTable';
import Modal from '../components/Modal';
import DataImportPanel from '../components/DataImportPanel';

const EMPTY = { name: '', semester: 5, strength: 55, program: 'CSE', year: 3 };

export default function SectionsPage() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState('');

  const load = () => { setLoading(true); getSections().then(r => { setData(r.data); setLoading(false); }); };
  useEffect(load, []);

  const handleSave = async () => {
    setError('');
    try {
      if (modal === 'create') await createSection(form);
      else await updateSection(form.id, form);
      setModal(null); load();
    } catch (e) { setError(e.response?.data?.detail || 'Error saving'); }
  };

  const columns = [
    { key: 'name', label: 'Name' },
    { key: 'semester', label: 'Semester' },
    { key: 'strength', label: 'Strength', render: (v) => v > 0 ? v : 'Not configured' },
    { key: 'program', label: 'Program' },
    { key: 'year', label: 'Year' },
    { key: 'active', label: 'Active', render: (v) => v ? 'Yes' : 'No' },
  ];

  return (
    <div>
      <div className="page-header">
        <h1>Sections</h1>
        <div className="page-actions">
          <DataImportPanel entity="sections" onImported={load}
            headings={['name', 'semester', 'strength', 'program', 'year', 'active']}
            sampleRow={['CSE-5A1', '5', '60', 'CSE', '3', 'Yes']} />
          <button className="btn btn-primary" onClick={() => { setForm(EMPTY); setModal('create'); }}>+ Add Section</button>
        </div>
      </div>
      <CrudTable columns={columns} data={data} loading={loading}
        onEdit={(row) => { setForm(row); setModal('edit'); }}
        onDelete={(id) => { if (confirm('Deactivate?')) deleteSection(id).then(load); }} />
      {modal && (
        <Modal title={modal === 'create' ? 'Add Section' : 'Edit Section'} onClose={() => setModal(null)}>
          {error && <div className="alert alert-error">{error}</div>}
          <div className="form-grid">
            <div className="form-group"><label>Name</label><input value={form.name} onChange={e => setForm({...form, name: e.target.value})} /></div>
            <div className="form-group"><label>Semester</label><input type="number" value={form.semester} onChange={e => setForm({...form, semester: parseInt(e.target.value)})} /></div>
            <div className="form-group"><label>Strength</label><input type="number" value={form.strength} onChange={e => setForm({...form, strength: parseInt(e.target.value)})} /></div>
            <div className="form-group"><label>Program</label><input value={form.program} onChange={e => setForm({...form, program: e.target.value})} /></div>
            <div className="form-group"><label>Year</label><input type="number" value={form.year} onChange={e => setForm({...form, year: parseInt(e.target.value)})} /></div>
          </div>
          <div className="modal-footer">
            <button className="btn btn-secondary" onClick={() => setModal(null)}>Cancel</button>
            <button className="btn btn-primary" onClick={handleSave}>Save</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
