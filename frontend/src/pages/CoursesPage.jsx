import { useState, useEffect } from 'react';
import { getCourses, createCourse, updateCourse, deleteCourse, getTeachers, getSections, importBatchFacultyWorkbook } from '../services/api';
import CrudTable from '../components/CrudTable';
import Modal from '../components/Modal';
import DataImportPanel from '../components/DataImportPanel';

const EMPTY = { course_code: '', course_name: '', course_type: 'lecture', credits: 3, weekly_sessions: 3, duration: 1, section_id: '', teacher_id: '', additional_teacher_ids: [], batch_label: '', link_group: '', required_room_type: 'lecture', priority: 5 };

export default function CoursesPage() {
  const [data, setData] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [sections, setSections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState('');
  const [batchFile, setBatchFile] = useState(null);
  const [batchImportBusy, setBatchImportBusy] = useState(false);
  const [batchImportResult, setBatchImportResult] = useState(null);

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
      const courseFields = { ...form };
      delete courseFields.credits;
      delete courseFields.additional_teacher_ids;
      const selectedTeacherIds = [...new Set([form.teacher_id, ...(form.additional_teacher_ids || [])]
        .map(Number).filter(Number.isInteger))];
      if (!selectedTeacherIds.length) {
        setError('Select at least one faculty member for this course.');
        return;
      }
      const payload = {
        ...courseFields,
        weekly_sessions: credits,
        section_id: parseInt(form.section_id),
        teacher_id: selectedTeacherIds[0],
        teacher_ids: selectedTeacherIds,
        batch_label: form.batch_label || null,
      };
      if (modal === 'create') await createCourse(payload);
      else await updateCourse(form.id, payload);
      setModal(null); load();
    } catch (e) { setError(e.response?.data?.detail || 'Error saving'); }
  };

  const handleBatchImport = async () => {
    if (!batchFile) return;
    setBatchImportBusy(true);
    setBatchImportResult(null);
    try {
      const { data: result } = await importBatchFacultyWorkbook(batchFile);
      setBatchImportResult(result);
      setBatchFile(null);
      await load();
    } catch (e) {
      const detail = e.response?.data?.detail;
      setBatchImportResult({
        message: detail?.message || (typeof detail === 'string' ? detail : 'The batch faculty workbook could not be imported.'),
        unresolved: detail?.errors || [],
      });
    } finally {
      setBatchImportBusy(false);
    }
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
    { key: 'batch_label', label: 'Batch', render: (v) => v || 'Whole section' },
    { key: 'teacher_ids', label: 'Faculty', render: (v, row) => (v?.length ? v : [row.teacher_id]).map(id => tMap[id] || `T${id}`).join(', ') },
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
      <section className="card" style={{ marginBottom: 18, padding: 18 }}>
        <div className="page-header" style={{ marginBottom: 8 }}>
          <div><h2 style={{ margin: 0, fontSize: 19 }}>Batch lab faculty workbook</h2><p className="text-muted" style={{ margin: '5px 0 0' }}>Import the college B1–B4 faculty sheet. The system combines B1 with B2 and B3 with B4, preserving each pair’s faculty and separate lab room.</p></div>
          <div className="page-actions">
            <input type="file" accept=".xlsx" onChange={event => setBatchFile(event.target.files?.[0] || null)} aria-label="Choose batch faculty workbook" />
            <button className="btn btn-primary" disabled={!batchFile || batchImportBusy} onClick={handleBatchImport}>{batchImportBusy ? 'Importing…' : 'Import batch faculty'}</button>
          </div>
        </div>
        {batchImportResult && <div className={`alert ${batchImportResult.unresolved?.length ? 'alert-warning' : 'alert-success'}`} role="status">
          <div>{batchImportResult.message}</div>
          {batchImportResult.unresolved?.length > 0 && <ul style={{ marginBottom: 0 }}>{batchImportResult.unresolved.map((item, index) => <li key={index}>{typeof item === 'string' ? item : JSON.stringify(item)}</li>)}</ul>}
        </div>}
      </section>
      <CrudTable columns={columns} data={data} loading={loading}
        onEdit={(row) => { setForm({ ...row, credits: row.weekly_sessions, teacher_id: String(row.teacher_id), additional_teacher_ids: (row.teacher_ids || []).filter(id => Number(id) !== Number(row.teacher_id)).map(String), batch_label: row.batch_label || '' }); setModal('edit'); }}
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
            <div className="form-group"><label>Lead faculty</label>
              <select value={form.teacher_id} onChange={e => setForm({...form, teacher_id: e.target.value, additional_teacher_ids: (form.additional_teacher_ids || []).filter(id => id !== e.target.value)})}>
                <option value="">Select faculty</option>
                {teachers.map(t => <option key={t.id} value={String(t.id)}>{t.name}</option>)}
              </select></div>
            <div className="form-group"><label>Additional faculty (optional)</label>
              <select multiple size="4" value={(form.additional_teacher_ids || []).filter(id => id !== String(form.teacher_id))}
                onChange={e => setForm({...form, additional_teacher_ids: [...e.target.selectedOptions].map(option => option.value)})}>
                {teachers.map(t => <option key={t.id} value={String(t.id)}>{t.name}</option>)}
              </select><span className="form-hint">Choose co-instructors who teach this same class, such as faculty assigned separately to B1 and B2.</span></div>
            <div className="form-group"><label>Batch</label>
              <select value={form.batch_label || ''} onChange={e => setForm({...form, batch_label: e.target.value})}>
                <option value="">Whole section</option><option value="B1/B2">B1 + B2</option><option value="B3/B4">B3 + B4</option>
              </select><span className="form-hint">Batch pairs apply to lab courses only. Paired students share one time and room.</span></div>
            <div className="form-group"><label>Parallel lab group (optional)</label>
              <input value={form.link_group || ''} onChange={e => setForm({...form, link_group: e.target.value})} maxLength="50" placeholder="For example: SEM5-LAB-BLOCK-1" />
              <span className="form-hint">Use the same group on different batch-pair lab courses when they must run together. Each pair gets a separate room; faculty conflicts are still blocked.</span></div>
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
