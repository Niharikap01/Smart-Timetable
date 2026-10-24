import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { createProgramElective, updateProgramElective, deleteProgramElective, getProgramElectives, getSections, getTeachers } from '../services/api';
import Modal from '../components/Modal';

const LARGE_ROOMS = 'DT-301, DT-701, DT-702';
const newGroup = (index) => ({ group_name: `Group ${index + 1}`, teacher_id: '', student_count: '', section_ids: [] });
const emptyForm = (semester) => ({ semester: Number(semester), course_code: '', course_name: '', periods_per_week: 1, groups: [newGroup(0)] });

function describeError(error) {
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(item => item.msg).filter(Boolean).join(' · ');
  return 'Could not save the program elective. Check the fields and try again.';
}

export default function ProgramElectivesPage() {
  const [semester, setSemester] = useState('5');
  const [sections, setSections] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [electives, setElectives] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState(emptyForm('5'));
  const [editingElectiveId, setEditingElectiveId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [accessDenied, setAccessDenied] = useState(false);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [sectionResponse, teacherResponse, electiveResponse] = await Promise.all([
        getSections({ semester: Number(semester), program: 'CSE' }),
        getTeachers({ active: true }),
        getProgramElectives(Number(semester)),
      ]);
      setSections(sectionResponse.data.filter(section => section.active));
      setTeachers(teacherResponse.data.filter(teacher => teacher.active));
      setElectives(electiveResponse.data);
      setAccessDenied(false);
    } catch (loadError) {
      const status = loadError.response?.status;
      setAccessDenied([401, 403].includes(status));
      setError(status === 401
        ? 'Sign in with a coordinator account to manage program electives.'
        : status === 403
          ? 'This account does not have coordinator permissions. Ask an administrator to provision a coordinator account.'
          : describeError(loadError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [semester]);

  const selectedSectionIds = useMemo(
    () => new Set(form.groups.flatMap(group => group.section_ids.map(Number))),
    [form.groups],
  );

  const updateGroup = (index, patch) => setForm(current => ({
    ...current,
    groups: current.groups.map((group, groupIndex) => groupIndex === index ? { ...group, ...patch } : group),
  }));

  const toggleSection = (groupIndex, sectionId) => {
    const group = form.groups[groupIndex];
    const id = Number(sectionId);
    const next = group.section_ids.includes(id)
      ? group.section_ids.filter(existingId => existingId !== id)
      : [...group.section_ids, id];
    updateGroup(groupIndex, { section_ids: next });
  };

  const openCreate = () => {
    setEditingElectiveId(null);
    setForm(emptyForm(semester));
    setError('');
    setNotice('');
    setModalOpen(true);
  };

  const openEdit = (elective) => {
    setEditingElectiveId(elective.id);
    setForm({
      semester: Number(elective.semester),
      course_code: elective.course_code,
      course_name: elective.course_name,
      periods_per_week: elective.periods_per_week,
      groups: elective.groups.map(group => ({
        group_name: group.group_name,
        teacher_id: String(group.teacher_id),
        student_count: String(group.student_count),
        section_ids: group.section_ids.map(Number),
      })),
    });
    setError('');
    setNotice('');
    setModalOpen(true);
  };

  const save = async (event) => {
    event.preventDefault();
    setError('');
    const invalidGroup = form.groups.find(group => !group.teacher_id || !Number(group.student_count) || group.section_ids.length === 0);
    if (invalidGroup) {
      setError('Each group needs a faculty member, student count, and at least one section.');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        ...form,
        semester: Number(semester),
        periods_per_week: Number(form.periods_per_week),
        groups: form.groups.map(group => ({
          ...group,
          teacher_id: Number(group.teacher_id),
          student_count: Number(group.student_count),
        })),
      };
      if (editingElectiveId === null) await createProgramElective(payload);
      else await updateProgramElective(editingElectiveId, payload);
      setModalOpen(false);
      setEditingElectiveId(null);
      setNotice(`${form.course_code.toUpperCase()} was ${editingElectiveId === null ? 'added' : 'updated'}. Regenerate Semester ${semester}; its timetable updates after a valid generation.`);
      await load();
    } catch (saveError) {
      const status = saveError.response?.status;
      setAccessDenied([401, 403].includes(status));
      setError(status === 401
        ? 'Sign in with a coordinator account to manage program electives.'
        : status === 403
          ? 'This account does not have coordinator permissions. Ask an administrator to provision a coordinator account.'
          : describeError(saveError));
      if ([401, 403].includes(status)) setModalOpen(false);
    } finally {
      setSaving(false);
    }
  };

  const remove = async (elective) => {
    if (!window.confirm(`Remove ${elective.course_code} from future timetable generation?`)) return;
    setError('');
    try {
      await deleteProgramElective(elective.id);
      setElectives(current => current.filter(item => item.id !== elective.id));
      setNotice(`${elective.course_code} was removed. Regenerate Semester ${semester}; its timetable updates after a valid generation.`);
    } catch (removeError) {
      const status = removeError.response?.status;
      setAccessDenied([401, 403].includes(status));
      setError(status === 401
        ? 'Sign in with a coordinator account to manage program electives.'
        : status === 403
          ? 'This account does not have coordinator permissions. Ask an administrator to provision a coordinator account.'
          : describeError(removeError));
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Program Electives</h1>
          <p>Create elective classes and combine sections that attend together.</p>
        </div>
        {!accessDenied && <button className="btn btn-primary" onClick={openCreate}>+ Add Program Elective</button>}
      </div>

      {accessDenied ? (
        <div className="card constraint-note">
          <h2>Coordinator access required</h2>
          <p>Program elective changes are restricted to coordinator and administrator accounts.</p>
          <Link className="btn btn-primary" to="/login">Sign in</Link>
        </div>
      ) : <>
      <div className="program-elective-controls card">
        <div className="form-group">
          <label htmlFor="elective-semester">Semester</label>
          <select id="elective-semester" value={semester} onChange={event => setSemester(event.target.value)}>
            {[1, 2, 3, 4, 5, 6, 7, 8].map(value => <option key={value} value={value}>Semester {value}</option>)}
          </select>
        </div>
        <p>Electives are stored for the selected semester. Sections grouped under one class receive the same time and room. Regenerate the semester after adding, editing, or removing an elective; the current timetable changes after a valid generation.</p>
      </div>

      {error && !modalOpen && <div className="alert alert-error">{error}</div>}
      {notice && <div className="alert alert-success">{notice} <Link to={`/generate?semester=${semester}`}>Generate updated timetable</Link></div>}

      {loading ? <div className="loading"><div className="spinner" /></div> : electives.length === 0 ? (
        <div className="card program-elective-empty">No program electives have been added for Semester {semester}.</div>
      ) : (
        <div className="program-elective-list">
          {electives.map(elective => (
            <article className="card program-elective-card" key={elective.id}>
              <div className="program-elective-card-header">
                <div>
                  <div className="program-elective-code">{elective.course_code}</div>
                  <h2>{elective.course_name}</h2>
                  <p>{elective.periods_per_week} period{elective.periods_per_week === 1 ? '' : 's'} per week</p>
                </div>
                <div className="program-elective-actions">
                  <button className="btn btn-secondary btn-sm" onClick={() => openEdit(elective)}>Edit</button>
                  <button className="btn btn-danger btn-sm" onClick={() => remove(elective)}>Remove</button>
                </div>
              </div>
              <div className="program-elective-groups">
                {elective.groups.map(group => (
                  <div className="program-elective-group" key={group.id}>
                    <div className="program-elective-group-heading">
                      <strong>{group.group_name}</strong>
                      <span>{group.student_count} students · {group.student_count > 70 ? `Large room only (${LARGE_ROOMS})` : 'Standard lecture room'}</span>
                    </div>
                    <div className="program-elective-group-details">
                      <span>Faculty: {group.teacher_name}</span>
                      <span>Sections together: {group.section_names.join(', ')}</span>
                    </div>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      )}

      {modalOpen && (
        <Modal title={`${editingElectiveId === null ? 'Add' : 'Edit'} Program Elective · Semester ${semester}`} onClose={() => !saving && setModalOpen(false)}>
          <form onSubmit={save}>
            {error && <div className="alert alert-error">{error}</div>}
            <div className="form-grid">
              <div className="form-group"><label>Course code</label><input required maxLength="50" value={form.course_code} onChange={event => setForm(current => ({ ...current, course_code: event.target.value }))} /></div>
              <div className="form-group"><label>Course name</label><input required maxLength="200" value={form.course_name} onChange={event => setForm(current => ({ ...current, course_name: event.target.value }))} /></div>
              <div className="form-group"><label>Periods per week</label><input type="number" min="1" max="30" required value={form.periods_per_week} onChange={event => setForm(current => ({ ...current, periods_per_week: event.target.value }))} /><span className="form-hint">Each period is scheduled as one class hour.</span></div>
            </div>

            <div className="program-elective-groups-form-header">
              <div><h3>Section groups</h3><p>Each group is one class: its sections share one faculty, time, and room.</p></div>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setForm(current => ({ ...current, groups: [...current.groups, newGroup(current.groups.length)] }))}>+ Add group</button>
            </div>

            {form.groups.map((group, index) => (
              <section className="program-elective-group-form" key={index}>
                <div className="form-grid">
                  <div className="form-group"><label>Group name</label><input required maxLength="100" value={group.group_name} onChange={event => updateGroup(index, { group_name: event.target.value })} /></div>
                  <div className="form-group"><label>Faculty for this class</label>
                    <select required value={group.teacher_id} onChange={event => updateGroup(index, { teacher_id: event.target.value })}>
                      <option value="">Select faculty</option>
                      {teachers.map(teacher => <option key={teacher.id} value={teacher.id}>{teacher.name} ({teacher.employee_id})</option>)}
                    </select>
                  </div>
                  <div className="form-group"><label>Total students in this grouped class</label><input type="number" min="1" max="1000" required value={group.student_count} onChange={event => updateGroup(index, { student_count: event.target.value })} /></div>
                </div>
                <div className="form-group">
                  <label>Sections that attend together</label>
                  {sections.length === 0 ? <p className="form-hint">No active CSE sections are registered for this semester.</p> : (
                    <div className="program-elective-section-options">
                      {sections.map(section => {
                        const checked = group.section_ids.includes(section.id);
                        const usedElsewhere = selectedSectionIds.has(section.id) && !checked;
                        return (
                          <label className={usedElsewhere ? 'program-elective-section disabled' : 'program-elective-section'} key={section.id}>
                            <input type="checkbox" checked={checked} disabled={usedElsewhere} onChange={() => toggleSection(index, section.id)} />
                            <span>{section.name}</span>
                          </label>
                        );
                      })}
                    </div>
                  )}
                  <span className="form-hint">{group.student_count > 70 ? `More than 70 students requires ${LARGE_ROOMS}.` : `Up to 70 students uses another active lecture room, not ${LARGE_ROOMS}.`}</span>
                </div>
                {form.groups.length > 1 && <button type="button" className="btn btn-danger btn-sm" onClick={() => setForm(current => ({ ...current, groups: current.groups.filter((_, groupIndex) => groupIndex !== index) }))}>Remove group</button>}
              </section>
            ))}

            <div className="modal-footer">
              <button type="button" className="btn btn-secondary" disabled={saving} onClick={() => setModalOpen(false)}>Cancel</button>
              <button type="submit" className="btn btn-primary" disabled={saving || sections.length === 0 || teachers.length === 0}>{saving ? 'Saving…' : editingElectiveId === null ? 'Save program elective' : 'Save changes'}</button>
            </div>
          </form>
        </Modal>
      )}
      </>}
    </div>
  );
}
