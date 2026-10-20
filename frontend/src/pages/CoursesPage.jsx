import { useState, useEffect } from 'react';
import { getCourses, createCourse, updateCourse, deleteCourse, getTeachers, getSections } from '../services/api';
import CrudTable from '../components/CrudTable';
import Modal from '../components/Modal';
import DataImportPanel from '../components/DataImportPanel';
import SectionStrengthEstimatePanel from '../components/SectionStrengthEstimatePanel';

const EMPTY = { course_code: '', course_name: '', course_type: 'lecture', credits: 3, weekly_sessions: 3, duration: 1, section_id: '', teacher_id: '', required_room_type: 'lecture', priority: 5 };

export default function CoursesPage() {
  const [data, setData] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [sections, setSections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState('');

  const load = () => {
    setLoading(true);
    Promise.all([getCourses(), getTeachers(), getSections()]).then(([c, t, s]) => {
      setData(c.data.filter(course => course.active && !course.program_elective_group_id));
      setTeachers(t.data.filter(teacher => teacher.active && !teacher.email?.toLowerCase().endsWith('@coordinator-import.local')));
      setSections(s.data);
      setLoading(false);
    });
  };
  useEffect(load, []);

  const handleSave = async () => {
    setError('');
    try {
      const credits = Number.parseInt(form.credits, 10);
      if (!Number.isInteger(credits) || credits < 1) {
        setError('Credits must be a whole number of at least 1.');
        return;
      }
      const { credits: _credits, ...courseFields } = form;
      const payload = {
        ...courseFields,
        weekly_sessions: credits,
        section_id: parseInt(form.section_id),
        teacher_id: parseInt(form.teacher_id),
      };
      if (modal === 'create') await createCourse(payload);
      else await updateCourse(form.id, payload);
      setModal(null); load();
    } catch (e) { setError(e.response?.data?.detail || 'Error saving'); }
  };

  const tMap = Object.fromEntries(teachers.map(t => [t.id, t.name]));
  const sMap = Object.fromEntries(sections.map(s => [s.id, s.name]));

  const columns = [
    { key: 'course_code', label: 'Code' },
    { key: 'course_name', label: 'Name' },
    { key: 'course_type', label: 'Type', render: (v) => <span className={`badge badge-${v === 'lab' ? 'lab' : 'lecture'}`}>{v}</span> },
    { key: 'weekly_sessions', label: 'Weekly' },
    { key: 'duration', label: 'Duration' },
    { key: 'section_id', label: 'Section', render: (v) => sMap[v] || v },
    { key: 'teacher_id', label: 'Teacher', render: (v) => tMap[v] || v },
    { key: 'required_room_type', label: 'Room Type' },
  ];

  return (
    <div>
      <div className="page-header">
        <h1>Courses</h1>
        <div className="page-actions">
          <DataImportPanel entity="courses" onImported={load}
            headings={['course_code', 'course_name', 'course_type', 'credits', 'duration', 'section', 'teacher_employee_id', 'required_room_type', 'priority', 'link_group', 'batch_label', 'active']}
            sampleRow={['24CS01TH0501', 'Machine Learning', 'lecture', '3', '1', 'CSE-5A1', 'CSE101', 'lecture', '5', '', '', 'Yes']} />
          <button className="btn btn-primary" onClick={() => { setForm(EMPTY); setModal('create'); }}>+ Add Course</button>
        </div>
      </div>
      <SectionStrengthEstimatePanel onUpdated={load} />
      <CrudTable columns={columns} data={data} loading={loading}
        onEdit={(row) => { setForm({ ...row, credits: row.weekly_sessions }); setModal('edit'); }}
        onDelete={(id) => { if (confirm('Deactivate?')) deleteCourse(id).then(load); }} />
      {modal && (
        <Modal title={modal === 'create' ? 'Add Course' : 'Edit Course'} onClose={() => setModal(null)}>
          {error && <div className="alert alert-error">{error}</div>}
          <div className="form-grid">
            <div className="form-group"><label>Course Code</label><input value={form.course_code} onChange={e => setForm({...form, course_code: e.target.value})} /></div>
            <div className="form-group"><label>Course Name</label><input value={form.course_name} onChange={e => setForm({...form, course_name: e.target.value})} /></div>
            <div className="form-group"><label>Type</label>
              <select value={form.course_type} onChange={e => setForm({...form, course_type: e.target.value})}>
                <option value="lecture">Lecture</option><option value="lab">Lab</option><option value="tutorial">Tutorial</option>
              </select></div>
            <div className="form-group"><label>Credits</label>
              <input type="number" min="1" value={form.credits ?? form.weekly_sessions} onChange={e => setForm({...form, credits: e.target.value})} />
              <span className="form-hint">1 credit = 1 lecture per week.</span>
            </div>
            <div className="form-group"><label>Lectures per Week</label><input value={form.credits ?? form.weekly_sessions} disabled /></div>
            <div className="form-group"><label>Duration (periods)</label><input type="number" value={form.duration} onChange={e => setForm({...form, duration: parseInt(e.target.value)})} /></div>
            <div className="form-group"><label>Section</label>
              <select value={form.section_id} onChange={e => setForm({...form, section_id: e.target.value})}>
                <option value="">Select</option>
                {sections.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select></div>
            <div className="form-group"><label>Teacher</label>
              <select value={form.teacher_id} onChange={e => setForm({...form, teacher_id: e.target.value})}>
                <option value="">Select</option>
                {teachers.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select></div>
            <div className="form-group"><label>Room Type</label>
              <select value={form.required_room_type} onChange={e => setForm({...form, required_room_type: e.target.value})}>
                <option value="lecture">Lecture</option><option value="lab">Lab</option>
              </select></div>
            <div className="form-group"><label>Priority (1-10)</label><input type="number" value={form.priority} onChange={e => setForm({...form, priority: parseInt(e.target.value)})} /></div>
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
