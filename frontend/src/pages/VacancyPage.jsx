import { useState, useEffect, useRef } from 'react';
import { getVacancyRooms, getVacancySummary } from '../services/api';

export default function VacancyPage() {
  const [rooms, setRooms] = useState([]);
  const [summary, setSummary] = useState({});
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [wsStatus, setWsStatus] = useState('disconnected');
  const [lastUpdated, setLastUpdated] = useState(null);
  const wsRef = useRef(null);

  const loadData = () => {
    getVacancyRooms().then(r => { setRooms(r.data); setLastUpdated(new Date()); });
    getVacancySummary().then(r => setSummary(r.data));
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000);
    connectWs();
    return () => { clearInterval(interval); wsRef.current?.close(); };
  }, []);

  const connectWs = () => {
    const ws = new WebSocket('ws://localhost:8000/ws/vacancy');
    ws.onopen = () => setWsStatus('connected');
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.event === 'INITIAL_STATE') {
        setRooms(data.rooms);
      } else if (data.event === 'ROOM_STATUS_CHANGED') {
        setRooms(prev => prev.map(r => r.room_id === data.room_id ? { ...r, ...data } : r));
      }
      setLastUpdated(new Date());
    };
    ws.onclose = () => {
      setWsStatus('disconnected');
      setTimeout(connectWs, 3000);
    };
    ws.onerror = () => ws.close();
    wsRef.current = ws;
  };

  const filtered = rooms.filter(r => {
    if (filter === 'free' && r.status !== 'FREE') return false;
    if (filter === 'occupied' && r.status !== 'OCCUPIED') return false;
    if (filter === 'lab' && r.room_type !== 'lab') return false;
    if (filter === 'lecture' && r.room_type !== 'lecture') return false;
    if (search && !r.room_number.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div>
      <div className="page-header">
        <h1>Room Vacancy</h1>
        <span className={`badge ${wsStatus === 'connected' ? 'badge-free' : 'badge-occupied'}`}>
          WS: {wsStatus}
        </span>
      </div>

      <div className="stats-grid">
        <div className="stat-card"><div className="label">Total Rooms</div><div className="value">{summary.total_rooms ?? 0}</div></div>
        <div className="stat-card"><div className="label">Occupied</div><div className="value" style={{color: 'var(--danger)'}}>{summary.occupied ?? 0}</div></div>
        <div className="stat-card"><div className="label">Free</div><div className="value" style={{color: 'var(--success)'}}>{summary.free ?? 0}</div></div>
        <div className="stat-card"><div className="label">Labs Free</div><div className="value">{summary.labs_free ?? 0}</div></div>
        <div className="stat-card"><div className="label">Classrooms Free</div><div className="value">{summary.classrooms_free ?? 0}</div></div>
        <div className="stat-card"><div className="label">Last Updated</div><div className="value" style={{fontSize: '0.9rem'}}>{lastUpdated?.toLocaleTimeString() ?? '—'}</div></div>
      </div>

      <div className="filters">
        <select value={filter} onChange={e => setFilter(e.target.value)}>
          <option value="all">All</option>
          <option value="free">Free</option>
          <option value="occupied">Occupied</option>
          <option value="lab">Labs</option>
          <option value="lecture">Classrooms</option>
        </select>
        <input placeholder="Search room number..." value={search} onChange={e => setSearch(e.target.value)} />
      </div>

      <div className="room-grid">
        {filtered.map(r => (
          <div key={r.room_id} className={`room-card ${r.status?.toLowerCase()}`}>
            <div className="room-header">
              <span className="room-number">{r.room_number}</span>
              <span className={`badge ${r.status === 'FREE' ? 'badge-free' : 'badge-occupied'}`}>{r.status}</span>
            </div>
            <div className="room-detail">Type: <span className={`badge badge-${r.room_type}`}>{r.room_type}</span></div>
            <div className="room-detail">Capacity: {r.capacity}</div>
            {r.status === 'OCCUPIED' && (
              <>
                <div className="room-detail" style={{marginTop: '0.5rem', fontWeight: 600}}>Course: {r.course}</div>
                <div className="room-detail">Section: {r.section}</div>
                <div className="room-detail">Teacher: {r.teacher}</div>
                <div className="room-detail">Slot: {r.timeslot}</div>
              </>
            )}
          </div>
        ))}
        {filtered.length === 0 && <div className="alert alert-info" style={{gridColumn: '1/-1'}}>No rooms match the filter.</div>}
      </div>
    </div>
  );
}
