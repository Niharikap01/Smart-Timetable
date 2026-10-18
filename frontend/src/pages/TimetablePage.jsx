import { useState, useEffect, useMemo } from 'react';
import { getSections, getTeachers, getRooms, getCourses, getTimeslots, getReservedSlots, getSectionTimetable, getTeacherTimetable, getRoomTimetable, getLatestTimetableSessions, previewMove, applyMove, previewSwap, applySwap } from '../services/api';

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const DEFAULT_SLOTS = [
  { idx: 0, label: '8:00-9:00' }, { idx: 1, label: '9:00-10:00' },
  { idx: 2, label: '10:00-11:00' }, { idx: 3, label: '11:00-12:00' },
  { idx: 4, label: '12:00-13:00' }, { idx: 5, label: '13:00-14:00' },
  { idx: 6, label: '14:00-15:00' }, { idx: 7, label: '15:00-16:00' },
  { idx: 8, label: '16:00-17:00' }, { idx: 9, label: '17:00-18:00' },
];

const isCoordinator = () => {
  try {
    const token = localStorage.getItem('token');
    if (!token) return false;
    const payload = JSON.parse(atob(token.split('.')[1]));
    // token may not carry role; optimistically enable edit UI and let server enforce 403
    return true;
  } catch { return false; }
};

export default function TimetablePage() {
  const canEdit = isCoordinator();
  const [viewType, setViewType] = useState('section');
  const [entityId, setEntityId] = useState('');
  const [sessions, setSessions] = useState([]);
  const [allSessions, setAllSessions] = useState([]);
  const [entities, setEntities] = useState([]);
  const [loading, setLoading] = useState(false);
  const [teachers, setTeachers] = useState({});
  const [teachersList, setTeachersList] = useState([]);
  const [rooms, setRooms] = useState({});
  const [roomsList, setRoomsList] = useState([]);
  const [sections, setSectionsMap] = useState({});
  const [courses, setCourses] = useState({});
  const [reservedSlots, setReservedSlots] = useState([]);
  const [timeslots, setTimeslots] = useState([]);
  const [editMode, setEditMode] = useState(false);
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [swapPick, setSwapPick] = useState(null);
  const [moveTarget, setMoveTarget] = useState(null); // {day, slotIdx}
  const [moveRoomId, setMoveRoomId] = useState('');
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState('');
  const [undoStack, setUndoStack] = useState([]);
  const [search, setSearch] = useState('');

  useEffect(() => {
    Promise.all([getSections(), getTeachers(), getRooms(), getCourses(), getReservedSlots(), getTimeslots()]).then(([s, t, r, c, reserved, slots]) => {
      setSectionsMap(Object.fromEntries(s.data.map(x => [x.id, x.name])));
      setTeachers(Object.fromEntries(t.data.map(x => [x.id, x.name])));
      setTeachersList(t.data);
      setRooms(Object.fromEntries(r.data.map(x => [x.id, x.room_number])));
      setRoomsList(r.data);
      setCourses(Object.fromEntries(c.data.map(x => [x.id, x])));
      setReservedSlots(reserved.data);
      setTimeslots(slots.data);
      if (viewType === 'section') setEntities(s.data);
      else if (viewType === 'teacher') setEntities(t.data);
      else setEntities(r.data);
    });
  }, []);

  useEffect(() => {
    Promise.all([getSections(), getTeachers(), getRooms()]).then(([s, t, r]) => {
      if (viewType === 'section') setEntities(s.data);
      else if (viewType === 'teacher') setEntities(t.data);
      else setEntities(r.data);
      setEntityId('');
      setSessions([]);
      setSelectedSessionId(null);
      setSwapPick(null);
      setPreview(null);
    });
  }, [viewType]);

  const loadTimetable = async () => {
    if (!entityId) return;
    setLoading(true);
    try {
      let res;
      if (viewType === 'section') res = await getSectionTimetable(entityId);
      else if (viewType === 'teacher') res = await getTeacherTimetable(entityId);
      else res = await getRoomTimetable(entityId);
      setSessions(res.data);
      // keep full schedule for swap context
      try { const all = await getLatestTimetableSessions(); setAllSessions(all.data); } catch {}
    } catch { setSessions([]); }
    setLoading(false);
  };

  const reloadAllSessions = async () => {
    try { const all = await getLatestTimetableSessions(); setAllSessions(all.data); } catch {}
  };

  useEffect(() => { if (entityId) loadTimetable(); }, [entityId]);

  // Keep undo target to revert: stash pre-move snapshot locally
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(''), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  const filteredEntities = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return entities;
    return entities.filter(e => String(e.name || e.room_number || '').toLowerCase().includes(q) || String(e.id).includes(q));
  }, [entities, search]);

  const timeslotByDaySlot = useMemo(() => {
    const m = new Map();
    for (const ts of timeslots) m.set(`${ts.day}::${ts.slot_index}`, ts);
    return m;
  }, [timeslots]);

  const getCell = (day, slotIdx) => {
    const masterSlot = timeslotByDaySlot.get(`${day}::${slotIdx}`);
    return sessions.filter(s => {
      const sDay = s.day;
      if (masterSlot) return sDay === day && Number(s.timeslot_id) === Number(masterSlot.id);
      const startHour = Number(String(s.start_time || '').split(':')[0]);
      const slotMatch = Number.isFinite(startHour) && startHour - 8 === slotIdx;
      return sDay === day && slotMatch;
    });
  };

  const reservationForCell = (day, slotIdx) => {
    if (viewType !== 'section') return null;
    const currentSection = Number(entityId);
    const matchingReservations = reservedSlots.filter(slot => slot.day === day && slot.slot_index === slotIdx);
    const sectionReservation = matchingReservations.find(slot => Number(slot.section_id) === currentSection);
    const globalReservation = matchingReservations.find(slot => slot.section_id == null);
    const timeslotReservation = timeslots.find(slot => slot.day === day && slot.slot_index === slotIdx && slot.is_reserved);
    const reservation = sectionReservation || globalReservation || timeslotReservation;
    if (!reservation) return null;
    const reason = String(reservation.reason || reservation.reservation_reason || 'Reserved').trim();
    const normalized = reason.toUpperCase();
    const isRecess = normalized.includes('RECESS') || normalized.includes('LUNCH');
    return {
      title: isRecess ? 'RECESS' : reason,
      detail: isRecess ? 'Academic recess · no class' : 'Department activity · fixed slot',
      isRecess,
    };
  };

  const displaySlots = Object.values(timeslots.reduce((byIndex, slot) => {
    if (!byIndex[slot.slot_index]) {
      const short = value => String(value || '').slice(0, 5).replace(/^0/, '');
      byIndex[slot.slot_index] = { idx: slot.slot_index, label: `${short(slot.start_time)}-${short(slot.end_time)}` };
    }
    return byIndex;
  }, {})).sort((a, b) => a.idx - b.idx);

  const handleSelectForMove = (slotDay, slotIdx) => {
    if (!editMode || !selectedSessionId) return;
    setMoveTarget({ day: slotDay, slotIdx });
    setPreview(null);
  };

  const doPreviewMove = async () => {
    if (!selectedSessionId || !moveTarget) return;
    setBusy(true);
    setPreview(null);
    try {
      const res = await previewMove({
        session_id: selectedSessionId,
        day: moveTarget.day,
        slot_index: moveTarget.slotIdx,
        room_id: moveRoomId ? Number(moveRoomId) : null,
      });
      setPreview(res.data);
    } catch (e) {
      const detail = e.response?.data?.detail;
      const violations = detail?.violations || [{ constraint: 'ERROR', message: e.response?.data?.detail?.message || e.message || 'Preview failed' }];
      setPreview({ valid: false, violations });
    }
    setBusy(false);
  };

  useEffect(() => {
    if (editMode && selectedSessionId && moveTarget) doPreviewMove();
  }, [moveRoomId]); // re-preview when room changes

  const doApplyMove = async () => {
    if (!selectedSessionId || !moveTarget) return;
    setBusy(true);
    // snapshot for local undo
    const snapshot = { sessionId: selectedSessionId, sessions: JSON.parse(JSON.stringify(sessions)), allSessions: JSON.parse(JSON.stringify(allSessions)) };
    setUndoStack(prev => [snapshot, ...prev].slice(0, 12));
    try {
      await applyMove({
        session_id: selectedSessionId,
        day: moveTarget.day,
        slot_index: moveTarget.slotIdx,
        room_id: moveRoomId ? Number(moveRoomId) : null,
      });
      setToast('Move applied. Vacancy updated.');
      setSelectedSessionId(null);
      setMoveTarget(null);
      setPreview(null);
      setMoveRoomId('');
      await loadTimetable();
      await reloadAllSessions();
    } catch (e) {
      const msg = e.response?.data?.detail?.violations?.[0]?.message || e.response?.data?.detail || e.message;
      setPreview({ valid: false, violations: [{ constraint: 'ERROR', message: String(msg) }] });
      setToast('');
    }
    setBusy(false);
  };

  const doPreviewSwap = async (aId, bId) => {
    setBusy(true);
    try {
      const res = await previewSwap({ a_session_id: aId, b_session_id: bId });
      setPreview(res.data);
    } catch (e) {
      const detail = e.response?.data?.detail;
      const violations = detail?.violations || [{ constraint: 'ERROR', message: String(detail?.message || detail || e.message) }];
      setPreview({ valid: false, violations });
    }
    setBusy(false);
  };

  const doApplySwap = async () => {
    if (!swapPick || !selectedSessionId || swapPick === selectedSessionId) return;
    const aId = selectedSessionId; const bId = swapPick;
    setBusy(true);
    const snapshot = { sessions: JSON.parse(JSON.stringify(sessions)), allSessions: JSON.parse(JSON.stringify(allSessions)) };
    setUndoStack(prev => [{ ...snapshot, swapIds: [aId, bId] }, ...prev].slice(0, 12));
    try {
      await applySwap({ a_session_id: aId, b_session_id: bId });
      setToast('Swap applied.');
      setSelectedSessionId(null);
      setSwapPick(null);
      setPreview(null);
      await loadTimetable();
      await reloadAllSessions();
    } catch (e) {
      const msg = e.response?.data?.detail?.violations?.[0]?.message || e.response?.data?.detail || e.message;
      setPreview({ valid: false, violations: [{ constraint: 'ERROR', message: String(msg) }] });
    }
    setBusy(false);
  };

  const handleUndo = async () => {
    const last = undoStack[0];
    if (!last) return;
    // Local revert: if we have a move snapshot with exact day/slot we can re-apply inverse via API
    // Simplest reliable undo: re-apply previous position by finding the session's old slot from snapshot
    const oldSess = (last.sessions || []).find(x => x.id === (last.sessionId || last.swapIds?.[0]));
    // For swap, swap back
    if (last.swapIds) {
      setBusy(true);
      try {
        await applySwap({ a_session_id: last.swapIds[0], b_session_id: last.swapIds[1] });
        setToast('Undone — swapped back.');
        await loadTimetable(); await reloadAllSessions();
      } catch (e) {
        setToast('Undo failed: ' + (e.response?.data?.detail?.violations?.[0]?.message || e.message));
      }
      setBusy(false);
      setUndoStack(prev => prev.slice(1));
      return;
    }
    if (oldSess && last.sessionId) {
      const ts = timeslotByDaySlot.get(`${oldSess.day}::${oldSess.slot_index ?? 0}`) || timeslots.find(x => x.id === oldSess.timeslot_id);
      // derive slot_index/day from snapshot reliably
      let day = oldSess.day;
      let slotIdx = 0;
      if (ts) slotIdx = ts.slot_index;
      else {
        // infer from sessions lookup
        const fullOld = last.allSessions?.find(x => x.id === last.sessionId);
        if (fullOld) {
          day = fullOld.day;
          const fullTs = timeslots.find(t => t.id === fullOld.timeslot_id);
          slotIdx = fullTs ? fullTs.slot_index : 0;
        }
      }
      setBusy(true);
      try {
        // reload timeslot map to get target slot
        const targetTs = timeslotByDaySlot.get(`${day}::${slotIdx}`);
        if (targetTs) {
          await applyMove({ session_id: last.sessionId, day: String(day), slot_index: Number(targetTs.slot_index), room_id: oldSess.room_id || null });
          setToast('Undone — moved back.');
          await loadTimetable(); await reloadAllSessions();
        } else {
          setToast('Undo: previous slot no longer exists.');
        }
      } catch (e) {
        setToast('Undo failed: ' + (e.response?.data?.detail?.violations?.[0]?.message || e.message));
      }
      setBusy(false);
      setUndoStack(prev => prev.slice(1));
      return;
    }
    setToast('Nothing to undo.');
    setUndoStack(prev => prev.slice(1));
  };

  const slotsToRender = displaySlots.length ? displaySlots : DEFAULT_SLOTS;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Timetable</h1>
          <p style={{ margin: '6px 0 0', color: 'var(--text-secondary)', fontSize: '13px' }}>
            {editMode ? 'Tap a class to select it, then tap an empty cell to preview the move. Pick a second class to swap.' : 'View by section, teacher, or room.'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {undoStack.length > 0 && <button className="btn btn-secondary btn-sm" onClick={handleUndo} disabled={busy}>Undo last</button>}
          <button className="btn btn-secondary" onClick={() => window.print()}>Print</button>
          <button
            className={`btn ${editMode ? 'btn-success' : 'btn-primary'}`}
            onClick={() => { setEditMode(v => !v); setSelectedSessionId(null); setSwapPick(null); setMoveTarget(null); setPreview(null); setMoveRoomId(''); }}
            title={canEdit ? '' : 'Login as coordinator to save edits'}
          >
            {editMode ? 'Exit edit' : 'Edit timetable'}
          </button>
        </div>
      </div>

      {editMode && (
        <div className="alert alert-info" style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', justifyContent: 'space-between' }}>
          <span>
            {selectedSessionId ? (
              swapPick && swapPick !== selectedSessionId ? 'Two classes selected — previewing swap.' : moveTarget ? `Move target: ${moveTarget.day} · slot ${moveTarget.slotIdx} — preview below.` : 'Class selected — tap an empty cell to choose the new time, or tap another class to swap.'
            ) : 'Tap any class cell to start. Esc to clear.'}
          </span>
          <span style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <label style={{ fontSize: '12px', fontWeight: 700 }}>Room (optional)</label>
            <select value={moveRoomId} onChange={e => setMoveRoomId(e.target.value)} style={{ minWidth: '140px' }}>
              <option value="">Keep same / auto-fit</option>
              {roomsList.map(r => <option key={r.id} value={r.id}>{r.room_number} ({r.room_type}, cap {r.capacity})</option>)}
            </select>
          </span>
        </div>
      )}

      {preview && (
        <div className={`alert ${preview.valid ? 'alert-success' : 'alert-error'}`} style={{ marginTop: '-8px' }}>
          <strong>{preview.valid ? '✓ Valid — ready to apply' : '✗ Blocked by constraints'}</strong>
          {preview.bundle_ids && preview.bundle_ids.length > 1 && <p style={{ margin: '6px 0 0' }}>Linked group: {preview.bundle_ids.length} parallel sessions will move together.</p>}
          {preview.violations?.length > 0 && (
            <ul style={{ margin: '8px 0 0', paddingLeft: '18px' }}>
              {preview.violations.map((v, i) => <li key={i}><strong>{v.constraint}:</strong> {v.message}</li>)}
            </ul>
          )}
          <div style={{ marginTop: '10px', display: 'flex', gap: '8px' }}>
            {preview.valid && selectedSessionId && moveTarget && !swapPick && <button className="btn btn-primary btn-sm" onClick={doApplyMove} disabled={busy}>Apply move</button>}
            {preview.valid && selectedSessionId && swapPick && <button className="btn btn-primary btn-sm" onClick={doApplySwap} disabled={busy}>Apply swap</button>}
            <button className="btn btn-secondary btn-sm" onClick={() => { setPreview(null); setMoveTarget(null); }}>Clear preview</button>
          </div>
        </div>
      )}

      {toast && <div className="alert alert-success">{toast}</div>}

      <div className="filters">
        <select value={viewType} onChange={e => { setViewType(e.target.value); }}>
          <option value="section">Section View</option>
          <option value="teacher">Teacher View</option>
          <option value="room">Room View</option>
        </select>
        <input placeholder="Search…" value={search} onChange={e => setSearch(e.target.value)} style={{ minWidth: '160px' }} />
        <select value={entityId} onChange={e => setEntityId(e.target.value)}>
          <option value="">Select {viewType}</option>
          {filteredEntities.map(e => (
            <option key={e.id} value={e.id}>{e.name || e.room_number || e.id}</option>
          ))}
        </select>
      </div>

      {loading && <div className="loading"><div className="spinner" /></div>}

      {!loading && entityId && (
        <div className="card timetable-grid">
          <table>
            <thead>
              <tr><th>Time</th>{DAYS.map(d => <th key={d}>{d}</th>)}</tr>
            </thead>
            <tbody>
              {slotsToRender.map(slot => (
                <tr key={slot.idx}>
                  <td style={{ fontWeight: 600, fontSize: '0.8rem', whiteSpace: 'nowrap' }}>{slot.label}</td>
                  {DAYS.map(day => {
                    const cellSessions = getCell(day, slot.idx);
                    const reservation = reservationForCell(day, slot.idx);
                    const isMoveTarget = moveTarget && moveTarget.day === day && moveTarget.slotIdx === slot.idx;
                    const isEmpty = cellSessions.length === 0 && !reservation;
                    return (
                      <td
                        key={day}
                        onClick={() => isEmpty && handleSelectForMove(day, slot.idx)}
                        style={isMoveTarget ? { background: '#ecfaf7', outline: '2px solid var(--teal-700)', outlineOffset: '-2px' } : (editMode && isEmpty && selectedSessionId ? { cursor: 'pointer', background: '#f8fafc' } : undefined)}
                        title={editMode && isEmpty && selectedSessionId ? 'Tap to set move target' : undefined}
                      >
                        {cellSessions.map((s) => {
                          const course = courses[s.course_id];
                          const isSelected = editMode && selectedSessionId === s.id;
                          const isSwapPick = editMode && swapPick === s.id;
                          return (
                          <div
                            key={s.id}
                            onClick={(e) => {
                              if (!editMode) return;
                              e.stopPropagation();
                              if (!selectedSessionId) {
                                setSelectedSessionId(s.id);
                                setSwapPick(null);
                                setMoveTarget(null);
                                setPreview(null);
                              } else if (selectedSessionId === s.id) {
                                setSelectedSessionId(null);
                                setSwapPick(null);
                                setMoveTarget(null);
                                setPreview(null);
                              } else if (!swapPick) {
                                // second pick => try swap preview
                                setSwapPick(s.id);
                                setMoveTarget(null);
                                doPreviewSwap(selectedSessionId, s.id);
                              } else {
                                setSwapPick(s.id);
                                doPreviewSwap(selectedSessionId, s.id);
                              }
                            }}
                            className={`tt-cell ${course?.course_type || 'lecture'} ${isSelected ? 'tt-selected' : ''} ${isSwapPick ? 'tt-swap-pick' : ''}`}
                            style={editMode ? { cursor: 'pointer', ...(isSelected ? { outline: '2px solid var(--blue-700)', outlineOffset: '1px' } : {}), ...(isSwapPick ? { outline: '2px solid var(--gold-600)', outlineOffset: '1px' } : {}) } : undefined}
                            role={editMode ? 'button' : undefined}
                            tabIndex={editMode ? 0 : undefined}
                          >
                            <div className="course">{course?.course_code || `Course #${s.course_id}`}</div>
                            <div className="course-name">{course?.course_name || 'Course details loading…'}</div>
                            <div className="info">{teachers[s.teacher_id] || `T${s.teacher_id}`}</div>
                            <div className="info">{rooms[s.room_id] || `R${s.room_id}`}</div>
                            {course?.duration > 1 && <div className="info duration">Two consecutive periods</div>}
                            {editMode && <div className="info" style={{ marginTop: '4px', fontWeight: 700, color: isSelected ? 'var(--blue-700)' : isSwapPick ? 'var(--gold-600)' : 'var(--text-muted)' }}>{isSelected ? 'Selected' : isSwapPick ? 'Swap with' : 'Tap to select'}</div>}
                          </div>
                          );
                        })}
                        {cellSessions.length === 0 && reservation && (
                          <div className={`tt-reserved ${reservation.isRecess ? 'tt-recess' : ''}`}>
                            <div className="course">{reservation.title}</div>
                            <div className="info">{reservation.detail}</div>
                          </div>
                        )}
                        {editMode && isEmpty && selectedSessionId && !reservation && (
                          <div className="info" style={{ color: 'var(--text-muted)', fontSize: '11px', padding: '6px 2px' }}>{isMoveTarget ? 'Target ✓ — preview below' : 'Tap to move here'}</div>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && entityId && sessions.length === 0 && (
        <div className="alert alert-info">No timetable data found. Generate a timetable first.</div>
      )}
      {!loading && !entityId && (
        <div className="alert alert-info">Pick a {viewType} above to view its timetable. Turn on <strong>Edit timetable</strong> to make on-time changes with constraint checks.</div>
      )}
    </div>
  );
}
