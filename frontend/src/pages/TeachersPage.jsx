import { useState, useEffect } from 'react';
import { getTeachers, createTeacher, updateTeacher, deleteTeacher } from '../services/api';
import CrudTable from '../components/CrudTable';
import Modal from '../components/Modal';
import DataImportPanel from '../components/DataImportPanel';

const EMPTY = { name: '', employee_id: '', email: '', faculty_type: 'regular', max_daily_hours: 7 };

export default function TeachersPage() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(null); // null | 'create' | 'edit'
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState('');

  const load = () => {
    setLoading(true);
    getTeachers().then(r => {
      setData(r.data.filter(teacher => !teacher.email?.toLowerCase().endsWith('@coordinator-import.local')));
      setLoading(false);
    });
  };
  useEffect(load, []);

  const handleSave = async () => {
    setError('');
    try {
      if (modal === 'create') await createTeacher(form);
      else await updateTeacher(form.id, form);
      setModal(null); load();
    } catch (e) { setError(e.response?.data?.detail || 'Error saving'); }
  };

  const handleDelete = async (id) => {
    if (!confirm('Deactivate this teacher?')) return;
    await deleteTeacher(id); load();
  };

  const columns = [
    { key: 'employee_id', label: 'Emp ID' },
    { key: 'name', label: 'Name' },
    { key: 'email', label: 'Email' },
    { key: 'faculty_type', label: 'Type', render: (v) => <span className={`badge badge-${v === 'visiting' ? 'occupied' : 'lecture'}`}>{v}</span> },
    { key: 'max_daily_hours', label: 'Max Hours' },
    { key: 'active', label: 'Active', render: (v) => v ? 'Yes' : 'No' },
  ];

  return (
    <div>
      <div className="page-header">
        <h1>Teachers</h1>
        <div className="page-actions">
          <DataImportPanel entity="teachers" onImported={load}
            headings={['name', 'employee_id', 'email', 'faculty_type', 'max_daily_hours', 'active']}
            sampleRow={['Dr. Priya Sharma', 'CSE101', 'priya.sharma@college.edu', 'regular', '7', 'Yes']} />
          <button className="btn btn-primary" onClick={() => { setForm(EMPTY); setModal('create'); }}>+ Add Teacher</button>
        </div>
      </div>
      <CrudTable columns={columns} data={data} loading={loading}
        onEdit={(row) => { setForm(row); setModal('edit'); }}
        onDelete={handleDelete} />

      {modal && (
        <Modal title={modal === 'create' ? 'Add Teacher' : 'Edit Teacher'} onClose={() => setModal(null)}>
          {error && <div className="alert alert-error">{error}</div>}
          <div className="form-grid">
            <div className="form-group"><label>Name</label><input value={form.name} onChange={e => setForm({...form, name: e.target.value})} /></div>
            <div className="form-group"><label>Employee ID</label><input value={form.employee_id} onChange={e => setForm({...form, employee_id: e.target.value})} disabled={modal === 'edit'} /></div>
            <div className="form-group"><label>Email</label><input value={form.email} onChange={e => setForm({...form, email: e.target.value})} /></div>
            <div className="form-group"><label>Faculty Type</label>
              <select value={form.faculty_type} onChange={e => setForm({...form, faculty_type: e.target.value})}>
                <option value="regular">Regular</option><option value="visiting">Visiting</option>
                <option value="senior">Senior</option><option value="contract">Contract</option>
              </select>
            </div>
            <div className="form-group"><label>Max Daily Hours</label><input type="number" value={form.max_daily_hours} onChange={e => setForm({...form, max_daily_hours: parseInt(e.target.value)})} /></div>
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
