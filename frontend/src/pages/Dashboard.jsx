import { useState, useEffect } from 'react';
import { getTeachers, getSections, getCourses, getRooms, getSchedules, healthCheck } from '../services/api';

export default function Dashboard() {
  const [stats, setStats] = useState({});
  const [status, setStatus] = useState('loading');
  const [latestSchedule, setLatestSchedule] = useState(null);

  useEffect(() => {
    Promise.all([
      getTeachers().then(r => r.data),
      getSections().then(r => r.data),
      getCourses().then(r => r.data),
      getRooms().then(r => r.data),
      getSchedules().then(r => r.data).catch(() => []),
      healthCheck().then(r => r.data).catch(() => null),
    ]).then(([teachers, sections, courses, rooms, schedules, health]) => {
      const activeCourses = courses.filter(course => course.active);
      setStats({
        teachers: teachers.length,
        sections: sections.length,
        courses: activeCourses.length,
        rooms: rooms.length,
        labs: rooms.filter(r => r.room_type === 'lab').length,
        classrooms: rooms.filter(r => r.room_type === 'lecture').length,
      });
      setLatestSchedule(schedules[0] || null);
      setStatus(health ? 'connected' : 'error');
    }).catch(() => setStatus('error'));
  }, []);

  const cards = [
    { label: 'Total Sections', value: stats.sections },
    { label: 'Total Teachers', value: stats.teachers },
    { label: 'Total Courses', value: stats.courses },
    { label: 'Total Rooms', value: stats.rooms },
    { label: 'Classrooms', value: stats.classrooms },
    { label: 'Labs', value: stats.labs },
  ];

  return (
    <div>
      <div className="page-header">
        <h1>Dashboard</h1>
        <span className={`badge ${status === 'connected' ? 'badge-free' : 'badge-occupied'}`}>
          {status === 'connected' ? 'System Online' : status === 'loading' ? 'Loading...' : 'Offline'}
        </span>
      </div>

      <div className="stats-grid">
        {cards.map((c) => (
          <div className="stat-card" key={c.label}>
            <div className="label">{c.label}</div>
            <div className="value">{c.value ?? '—'}</div>
          </div>
        ))}
      </div>

      {latestSchedule && (
        <div className="card" style={{ marginTop: '1rem' }}>
          <h3 style={{ marginBottom: '0.75rem' }}>Latest Generated Schedule</h3>
          <p><strong>Status:</strong> <span className={`badge ${latestSchedule.status === 'VALID' ? 'badge-free' : 'badge-occupied'}`}>{latestSchedule.status}</span></p>
          <p><strong>Generated:</strong> {new Date(latestSchedule.generated_at).toLocaleString()}</p>
          <p><strong>Hard Violations:</strong> {latestSchedule.hard_constraint_violations}</p>
          <p><strong>Soft Score:</strong> {latestSchedule.soft_constraint_score?.toFixed(1) ?? '—'}</p>
          <p><strong>Time:</strong> {latestSchedule.generation_time_ms}ms</p>
        </div>
      )}
    </div>
  );
}
