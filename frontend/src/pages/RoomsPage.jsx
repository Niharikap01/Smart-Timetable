import { useState, useEffect } from 'react';
import { getRooms, createRoom, updateRoom, deleteRoom } from '../services/api';
import CrudTable from '../components/CrudTable';
import Modal from '../components/Modal';
import DataImportPanel from '../components/DataImportPanel';

const EMPTY = { room_number: '', room_type: 'lecture', capacity: 60, building: '', floor: 1 };

export default function RoomsPage() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState('');

  const load = () => { setLoading(true); getRooms().then(r => { setData(r.data); setLoading(false); }); };
  useEffect(load, []);

  const handleSave = async () => {
    setError('');
    try {
      if (modal === 'create') await createRoom(form);
      else await updateRoom(form.id, form);
      setModal(null); load();
    } catch (e) { setError(e.response?.data?.detail || 'Error saving'); }
  };

  const columns = [
    { key: 'room_number', label: 'Room Number' },
    { key: 'room_type', label: 'Type', render: (v) => <span className={`badge badge-${v}`}>{v}</span> },
    { key: 'capacity', label: 'Capacity', render: (v) => v > 0 ? v : 'Not configured' },
    { key: 'building', label: 'Building' },
    { key: 'floor', label: 'Floor' },
    { key: 'active', label: 'Active', render: (v) => v ? 'Yes' : 'No' },
  ];

  return (
    <div>
      <div className="page-header">
        <h1>Rooms</h1>
        <div className="page-actions">
          <DataImportPanel entity="rooms" onImported={load}
            headings={['room_number', 'room_type', 'capacity', 'building', 'floor', 'active']}
            sampleRow={['DT-203', 'lecture', '70', 'Department Block', '2', 'Yes']} />
          <button className="btn btn-primary" onClick={() => { setForm(EMPTY); setModal('create'); }}>+ Add Room</button>
        </div>
      </div>
      <CrudTable columns={columns} data={data} loading={loading}
        onEdit={(row) => { setForm(row); setModal('edit'); }}
        onDelete={(id) => { if (confirm('Deactivate?')) deleteRoom(id).then(load); }} />
      {modal && (
        <Modal title={modal === 'create' ? 'Add Room' : 'Edit Room'} onClose={() => setModal(null)}>
          {error && <div className="alert alert-error">{error}</div>}
          <div className="form-grid">
            <div className="form-group"><label>Room Number</label><input value={form.room_number} onChange={e => setForm({...form, room_number: e.target.value})} /></div>
            <div className="form-group"><label>Type</label>
              <select value={form.room_type} onChange={e => setForm({...form, room_type: e.target.value})}>
                <option value="lecture">Lecture</option><option value="lab">Lab</option>
              </select></div>
            <div className="form-group"><label>Capacity</label><input type="number" value={form.capacity} onChange={e => setForm({...form, capacity: parseInt(e.target.value)})} /></div>
            <div className="form-group"><label>Building</label><input value={form.building || ''} onChange={e => setForm({...form, building: e.target.value})} /></div>
            <div className="form-group"><label>Floor</label><input type="number" value={form.floor || ''} onChange={e => setForm({...form, floor: parseInt(e.target.value)})} /></div>
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
