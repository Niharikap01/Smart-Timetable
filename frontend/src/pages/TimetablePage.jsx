import { useState, useEffect, useMemo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { getCurrentUser, getSections, getTeachers, getRooms, getCourses, getTimeslots, getReservedSlots, getSectionTimetable, getTeacherTimetable, getRoomTimetable, getLatestTimetableSessions, previewMove, applyMove, previewSwap, applySwap } from '../services/api';

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const DEFAULT_SLOTS = [
  { idx: 0, label: '8:00-9:00' }, { idx: 1, label: '9:00-10:00' },
  { idx: 2, label: '10:00-11:00' }, { idx: 3, label: '11:00-12:00' },
  { idx: 4, label: '12:00-13:00' }, { idx: 5, label: '13:00-14:00' },
  { idx: 6, label: '14:00-15:00' }, { idx: 7, label: '15:00-16:00' },
  { idx: 8, label: '16:00-17:00' }, { idx: 9, label: '17:00-18:00' },
];

export default function TimetablePage() {
  const [canEdit, setCanEdit] = useState(false);
  const [accessChecked, setAccessChecked] = useState(false);
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
  const [editAction, setEditAction] = useState('move');
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [swapPick, setSwapPick] = useState(null);
  const [moveTarget, setMoveTarget] = useState(null); // {day, slotIdx}
  const [moveRoomId, setMoveRoomId] = useState('');
  const [moveTeacherId, setMoveTeacherId] = useState('');
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState('');
  const [undoStack, setUndoStack] = useState([]);
  const [search, setSearch] = useState('');

  useEffect(() => {
    let active = true;
    if (!localStorage.getItem('token')) {
      setCanEdit(false);
      setAccessChecked(true);
      return () => { active = false; };
    }
    getCurrentUser()
      .then(({ data }) => { if (active) setCanEdit(Boolean(data.is_admin || data.is_coordinator)); })
      .catch(() => { if (active) setCanEdit(false); })
      .finally(() => { if (active) setAccessChecked(true); });
    return () => { active = false; };
  }, []);

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
      setMoveTarget(null);
      setMoveRoomId('');
      setMoveTeacherId('');
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
    const viewEntities = viewType === 'teacher'
      ? entities.filter(teacher => !/^FACULTY_/i.test(teacher.employee_id || ''))
      : entities;
    const q = search.trim().toLowerCase();
    if (!q) return viewEntities;
    return viewEntities.filter(e => String(e.name || e.room_number || '').toLowerCase().includes(q) || String(e.id).includes(q));
  }, [entities, search, viewType]);

  const timeslotByDaySlot = useMemo(() => {
    const m = new Map();
    for (const ts of timeslots) m.set(`${ts.day}::${ts.slot_index}`, ts);
    return m;
  }, [timeslots]);
  const timeslotById = useMemo(() => new Map(timeslots.map(slot => [Number(slot.id), slot])), [timeslots]);

  const selectedSession = useMemo(
    () => allSessions.find(session => Number(session.id) === Number(selectedSessionId))
      || sessions.find(session => Number(session.id) === Number(selectedSessionId))
      || null,
    [allSessions, sessions, selectedSessionId],
  );
  const selectedTimeslot = selectedSession
    ? timeslots.find(slot => Number(slot.id) === Number(selectedSession.timeslot_id))
    : null;
  const previewAffectedSections = useMemo(() => {
    const ids = new Set([
      ...(preview?.bundle_ids || []),
      ...(preview?.a_bundle_ids || []),
      ...(preview?.b_bundle_ids || []),
    ].map(Number));
    return [...new Set(allSessions.filter(session => ids.has(Number(session.id)))
      .map(session => sections[session.section_id]).filter(Boolean))];
  }, [preview, allSessions, sections]);

  const getCell = (day, slotIdx) => {
    const masterSlot = timeslotByDaySlot.get(`${day}::${slotIdx}`);
    if (viewType === 'section') {
      return sessions.flatMap(session => {
        if (session.day !== day) return [];
        const startSlot = timeslotById.get(Number(session.timeslot_id))?.slot_index;
        if (!Number.isInteger(startSlot)) return [];
        const duration = Number(courses[session.course_id]?.duration || 1);
        if (slotIdx < startSlot || slotIdx >= startSlot + duration) return [];
        return [{ ...session, isContinuation: slotIdx > startSlot }];
      });
    }
    const matchingSessions = sessions.filter(s => {
      const sDay = s.day;
      if (masterSlot) return sDay === day && Number(s.timeslot_id) === Number(masterSlot.id);
      const startHour = Number(String(s.start_time || '').split(':')[0]);
      const slotMatch = Number.isFinite(startHour) && startHour - 8 === slotIdx;
      return sDay === day && slotMatch;
    });
    if (viewType === 'section') return matchingSessions;
    const seenElectiveClasses = new Set();
    return matchingSessions.filter(session => {
      const groupId = courses[session.course_id]?.program_elective_group_id;
      if (groupId == null) return true;
      const classKey = `${groupId}:${session.day}:${session.timeslot_id}`;
      if (seenElectiveClasses.has(classKey)) return false;
      seenElectiveClasses.add(classKey);
      return true;
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
    if (isRecess) {
      // Recess is a break during a student's teaching day, not a class to
      // attend after their last lesson. The master timetable reserves one
      // break slot per weekday, so hide it when this section has no teaching
      // on both sides of that slot (for example, Monday's classes end at 12).
      const daySessions = sessions.filter(session => session.day === day);
      const cohorts = [...new Set(daySessions.flatMap(session => {
        const label = String(session.batch_label || courses[session.course_id]?.batch_label || '').toUpperCase();
        return [...label.matchAll(/B\s*([1-4])/g)].map(([, batch]) => batch);
      }))];
      const attendanceGroups = cohorts.length ? cohorts : [null];
      const recessIsBetweenClasses = attendanceGroups.some(batch => {
        let hasClassBefore = false;
        let hasClassAfter = false;
        for (const session of daySessions) {
          const course = courses[session.course_id];
          const label = String(session.batch_label || course?.batch_label || '').toUpperCase();
          const sessionBatches = [...label.matchAll(/B\s*([1-4])/g)].map(([, number]) => number);
          if (batch && sessionBatches.length && !sessionBatches.includes(batch)) continue;

          const startSlot = timeslotById.get(Number(session.timeslot_id))?.slot_index;
          if (!Number.isInteger(startSlot)) continue;
          const endSlot = startSlot + Number(course?.duration || 1);
          if (endSlot <= slotIdx) hasClassBefore = true;
          if (startSlot > slotIdx) hasClassAfter = true;
          if (hasClassBefore && hasClassAfter) return true;
        }
        return false;
      });
      if (!recessIsBetweenClasses) return null;
    }
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
    if (!editMode || editAction !== 'move' || !selectedSessionId) return;
    setMoveTarget({ day: slotDay, slotIdx });
    setPreview(null);
  };

  const doPreviewMove = useCallback(async () => {
    if (!selectedSessionId || !moveTarget) return;
    setBusy(true);
    setPreview(null);
    try {
      const res = await previewMove({
        session_id: selectedSessionId,
        day: moveTarget.day,
        slot_index: moveTarget.slotIdx,
        room_id: moveRoomId && Number(moveRoomId) !== Number(selectedSession?.room_id) ? Number(moveRoomId) : null,
        teacher_id: moveTeacherId ? Number(moveTeacherId) : null,
      });
      setPreview(res.data);
    } catch (e) {
      const detail = e.response?.data?.detail;
      const violations = detail?.violations || [{ constraint: 'ERROR', message: e.response?.data?.detail?.message || e.message || 'Preview failed' }];
      setPreview({ valid: false, violations });
    }
    setBusy(false);
  }, [selectedSessionId, selectedSession, moveTarget, moveRoomId, moveTeacherId]);

  useEffect(() => {
    if (editMode && editAction === 'move' && selectedSessionId && moveTarget) doPreviewMove();
  }, [editMode, editAction, selectedSessionId, moveTarget, doPreviewMove]);

  const handleSelectSession = (session) => {
    if (!editMode) return;
    if (!selectedSessionId || (editAction === 'move' && selectedSessionId !== session.id)) {
      setSelectedSessionId(session.id);
      setSwapPick(null);
      setMoveTarget(null);
      setPreview(null);
      setMoveRoomId('');
      setMoveTeacherId('');
      return;
    }
    if (selectedSessionId === session.id) {
      setSelectedSessionId(null);
      setSwapPick(null);
      setMoveTarget(null);
      setPreview(null);
      setMoveRoomId('');
      setMoveTeacherId('');
      return;
    }
    if (editAction === 'swap') {
      setSwapPick(session.id);
      setMoveTarget(null);
      setPreview(null);
      doPreviewSwap(selectedSessionId, session.id);
    }
  };

  const handlePreviewSameTimeChange = () => {
    if (!selectedSession || !selectedTimeslot) return;
    setMoveTarget({ day: selectedSession.day, slotIdx: selectedTimeslot.slot_index });
    setPreview(null);
  };

  const doApplyMove = async () => {
    if (!selectedSessionId || !moveTarget) return;
    setBusy(true);
    const selectedCourse = selectedSession ? courses[selectedSession.course_id] : null;
    const snapshot = {
      sessionId: selectedSessionId,
      sessions: JSON.parse(JSON.stringify(sessions)),
      allSessions: JSON.parse(JSON.stringify(allSessions)),
      isLinkedCourseGroup: Boolean(selectedCourse?.link_group && selectedCourse?.program_elective_group_id == null),
    };
    try {
      const response = await applyMove({
        session_id: selectedSessionId,
        day: moveTarget.day,
        slot_index: moveTarget.slotIdx,
        room_id: moveRoomId && Number(moveRoomId) !== Number(selectedSession?.room_id) ? Number(moveRoomId) : null,
        teacher_id: moveTeacherId ? Number(moveTeacherId) : null,
      });
      snapshot.preserveGroupRooms = snapshot.isLinkedCourseGroup && response.data.bundle_ids?.length > 1;
      setUndoStack(prev => [snapshot, ...prev].slice(0, 12));
      setToast('Change saved to the timetable. Vacancy information was refreshed.');
      setSelectedSessionId(null);
      setMoveTarget(null);
      setPreview(null);
      setMoveRoomId('');
      setMoveTeacherId('');
      await loadTimetable();
      await reloadAllSessions();
    } catch (e) {
      const msg = e.response?.data?.detail?.violations?.[0]?.message || e.response?.data?.detail || e.message;
      setPreview({ valid: false, violations: [{ constraint: 'ERROR', message: String(msg) }] });
      setToast('');
    }
    setBusy(false);
  };

  async function doPreviewSwap(aId, bId) {
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
  }

  const doApplySwap = async () => {
    if (!swapPick || !selectedSessionId || swapPick === selectedSessionId) return;
    const aId = selectedSessionId; const bId = swapPick;
    setBusy(true);
    const snapshot = { sessions: JSON.parse(JSON.stringify(sessions)), allSessions: JSON.parse(JSON.stringify(allSessions)) };
    try {
      await applySwap({ a_session_id: aId, b_session_id: bId });
      setUndoStack(prev => [{ ...snapshot, swapIds: [aId, bId] }, ...prev].slice(0, 12));
      setToast('Swap saved to the timetable.');
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
      let undone = false;
      try {
        await applySwap({ a_session_id: last.swapIds[0], b_session_id: last.swapIds[1] });
        setToast('Previous timetable restored and saved.');
        await loadTimetable(); await reloadAllSessions();
        undone = true;
      } catch (e) {
        setToast('Undo failed: ' + (e.response?.data?.detail?.violations?.[0]?.message || e.message));
      }
      setBusy(false);
      if (undone) setUndoStack(prev => prev.slice(1));
      return;
    }
    if (oldSess && last.sessionId) {
      const ts = timeslots.find(x => Number(x.id) === Number(oldSess.timeslot_id)) || timeslotByDaySlot.get(`${oldSess.day}::${oldSess.slot_index ?? 0}`);
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
      let undone = false;
      try {
        // reload timeslot map to get target slot
        const targetTs = timeslotByDaySlot.get(`${day}::${slotIdx}`);
        if (targetTs) {
          await applyMove({ session_id: last.sessionId, day: String(day), slot_index: Number(targetTs.slot_index), room_id: last.preserveGroupRooms ? null : oldSess.room_id || null, teacher_id: oldSess.teacher_id || null });
          setToast('Previous timetable restored and saved.');
          await loadTimetable(); await reloadAllSessions();
          undone = true;
        } else {
          setToast('Undo: previous slot no longer exists.');
        }
      } catch (e) {
        setToast('Undo failed: ' + (e.response?.data?.detail?.violations?.[0]?.message || e.message));
      }
      setBusy(false);
      if (undone) setUndoStack(prev => prev.slice(1));
      return;
    }
    setToast('Nothing to undo.');
    setUndoStack(prev => prev.slice(1));
  };

  const slotsToRender = displaySlots.length ? displaySlots : DEFAULT_SLOTS;
  const proposedSlot = moveTarget && slotsToRender.find(slot => slot.idx === moveTarget.slotIdx);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Timetable</h1>
          <p style={{ margin: '6px 0 0', color: 'var(--text-secondary)', fontSize: '13px' }}>
            {editMode ? 'Make a last-minute change, review the constraint check, then save it to the timetable.' : 'View by section, teacher, or room.'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {undoStack.length > 0 && <button className="btn btn-secondary btn-sm" onClick={handleUndo} disabled={busy}>Undo last</button>}
          <button className="btn btn-secondary" onClick={() => window.print()}>Print</button>
          {accessChecked && canEdit && <button
              className={`btn ${editMode ? 'btn-success' : 'btn-primary'}`}
              onClick={() => { setEditMode(v => !v); setSelectedSessionId(null); setSwapPick(null); setMoveTarget(null); setPreview(null); setMoveRoomId(''); setMoveTeacherId(''); setEditAction('move'); }}
            >
              {editMode ? 'Finish editing' : 'Edit timetable'}
            </button>}
        </div>
      </div>

      {accessChecked && !canEdit && <div className="alert alert-info timetable-access-note">Coordinator access is required to save timetable changes. <Link to="/login">Sign in</Link></div>}

      {editMode && (
        <div className="card timetable-edit-panel">
          <div className="timetable-edit-heading">
            <div>
              <span className="timetable-edit-kicker">Coordinator tools</span>
              <h2>Make a timetable change</h2>
              <p>Every change is checked against the scheduling rules before it can be saved.</p>
            </div>
            <div className="timetable-edit-actions">
              <button type="button" aria-pressed={editAction === 'move'} className={`btn btn-sm ${editAction === 'move' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => { setEditAction('move'); setSelectedSessionId(null); setSwapPick(null); setMoveTarget(null); setPreview(null); setMoveRoomId(''); setMoveTeacherId(''); }}>Move / change a class</button>
              <button type="button" aria-pressed={editAction === 'swap'} className={`btn btn-sm ${editAction === 'swap' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => { setEditAction('swap'); setSelectedSessionId(null); setSwapPick(null); setMoveTarget(null); setPreview(null); setMoveRoomId(''); setMoveTeacherId(''); }}>Swap two classes</button>
            </div>
          </div>

          <div className="timetable-edit-steps">
            {editAction === 'move' ? (
                  <p><strong>Move / change:</strong> 1. Select a class. 2. Select an open day and time, or choose a room/faculty change below. 3. Review the check and choose <strong>Apply &amp; save move</strong>.</p>
            ) : (
              <p><strong>Swap:</strong> 1. Select the first class. 2. Select the second class. 3. Review the check and choose <strong>Apply &amp; save swap</strong>.</p>
            )}
          </div>

          {selectedSession && (
            <div className="timetable-edit-selection">
              <div>
                <span className="timetable-edit-kicker">Selected class</span>
                <strong>{courses[selectedSession.course_id]?.course_code || `Course #${selectedSession.course_id}`} · {courses[selectedSession.course_id]?.course_name || 'Course details loading…'}</strong>
                <span>{sections[selectedSession.section_id] || `Section ${selectedSession.section_id}`} · {selectedSession.day} · {selectedTimeslot?.start_time?.slice(0, 5) || ''}–{selectedTimeslot?.end_time?.slice(0, 5) || ''} · {teachers[selectedSession.teacher_id] || `Faculty ${selectedSession.teacher_id}`} · {rooms[selectedSession.room_id] || `Room ${selectedSession.room_id}`}</span>
              </div>
              <div className="timetable-edit-selection-actions">
                {editAction === 'move' && <>
                  <label className="timetable-room-select"><span>Room after change</span>
                    <select value={moveRoomId} onChange={event => setMoveRoomId(event.target.value)}>
                      <option value="">Keep current room</option>
                      {roomsList.filter(room => room.active).map(room => <option key={room.id} value={room.id}>{room.room_number} · {room.room_type} · {room.capacity} seats</option>)}
                    </select>
                  </label>
                  <label className="timetable-room-select"><span>Faculty after change</span>
                    <select value={moveTeacherId} onChange={event => setMoveTeacherId(event.target.value)}>
                      <option value="">Keep current faculty</option>
                      {teachersList.filter(teacher => teacher.active).map(teacher => <option key={teacher.id} value={teacher.id}>{teacher.name} · {teacher.employee_id}</option>)}
                    </select>
                  </label>
                  <button type="button" className="btn btn-secondary btn-sm" onClick={handlePreviewSameTimeChange} disabled={!selectedTimeslot || ((!moveRoomId || Number(moveRoomId) === Number(selectedSession.room_id)) && (!moveTeacherId || Number(moveTeacherId) === Number(selectedSession.teacher_id)))}>Preview room/faculty change at this time</button>
                </>}
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => { setSelectedSessionId(null); setSwapPick(null); setMoveTarget(null); setPreview(null); setMoveRoomId(''); setMoveTeacherId(''); }}>Clear selection</button>
              </div>
            </div>
          )}
          {busy && !preview && <p className="timetable-checking">Checking this change against timetable rules…</p>}
        </div>
      )}

      {preview && (
        <div className={`alert ${preview.valid ? 'alert-success' : 'alert-error'}`} style={{ marginTop: '-8px' }}>
          <strong>{preview.valid ? '✓ Constraint check passed' : '✗ This change is blocked'}</strong>
          {preview.valid && <p style={{ margin: '6px 0 0' }}>The timetable is still valid. Applying the change will save it to the generated schedule.</p>}
          {editAction === 'move' && moveTarget && <p style={{ margin: '6px 0 0' }}>Proposed: {moveTarget.day} · {proposedSlot?.label || `Period ${moveTarget.slotIdx + 1}`} · {moveRoomId ? (roomsList.find(room => Number(room.id) === Number(moveRoomId))?.room_number || 'selected room') : 'current room'} · {moveTeacherId ? (teachers[moveTeacherId] || 'selected faculty') : 'current faculty'}.</p>}
          {previewAffectedSections.length > 1 && <p style={{ margin: '6px 0 0' }}>Sections moving together: {previewAffectedSections.join(', ')}.</p>}
          {preview.violations?.length > 0 && (
            <ul style={{ margin: '8px 0 0', paddingLeft: '18px' }}>
              {preview.violations.map((v, i) => <li key={i}><strong>{v.constraint}:</strong> {v.message}</li>)}
            </ul>
          )}
          <div style={{ marginTop: '10px', display: 'flex', gap: '8px' }}>
            {preview.valid && selectedSessionId && moveTarget && editAction === 'move' && <button className="btn btn-primary btn-sm" onClick={doApplyMove} disabled={busy}>{busy ? 'Saving…' : 'Apply & save move'}</button>}
            {preview.valid && selectedSessionId && swapPick && editAction === 'swap' && <button className="btn btn-primary btn-sm" onClick={doApplySwap} disabled={busy}>{busy ? 'Saving…' : 'Apply & save swap'}</button>}
            {busy && !preview.valid && <span className="timetable-checking">Checking this change against timetable rules…</span>}
            <button className="btn btn-secondary btn-sm" onClick={() => { setPreview(null); setMoveTarget(null); setSwapPick(null); }}>Clear preview</button>
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
        <select value={entityId} onChange={e => { setEntityId(e.target.value); setSelectedSessionId(null); setSwapPick(null); setMoveTarget(null); setMoveRoomId(''); setMoveTeacherId(''); setPreview(null); }}>
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
              <tr><th className="timetable-corner">Day / time</th>{slotsToRender.map(slot => <th key={slot.idx}>{slot.label}</th>)}</tr>
            </thead>
            <tbody>
              {DAYS.map(day => {
                let coveredUntil = -1;
                return (
                  <tr key={day}>
                    <th scope="row" className="timetable-day">{day}</th>
                    {slotsToRender.map((slot, slotPosition) => {
                      if (slot.idx < coveredUntil) return null;
                    const cellSessions = getCell(day, slot.idx);
                    const reservation = reservationForCell(day, slot.idx);
                    const isMoveTarget = moveTarget && moveTarget.day === day && moveTarget.slotIdx === slot.idx;
                    const isEmpty = cellSessions.length === 0 && !reservation;
                    const spanDuration = Math.max(1, ...cellSessions.map(session => Number(courses[session.course_id]?.duration || 1)));
                    const columnSpan = viewType === 'section' ? 1 : Math.min(spanDuration, slotsToRender.length - slotPosition);
                    if (cellSessions.length > 0) coveredUntil = slot.idx + columnSpan;
                    return (
                      <td
                        key={`${day}-${slot.idx}`}
                        colSpan={columnSpan}
                        onClick={() => isEmpty && handleSelectForMove(day, slot.idx)}
                        style={isMoveTarget ? { background: '#ecfaf7', outline: '2px solid var(--teal-700)', outlineOffset: '-2px' } : (editMode && isEmpty && selectedSessionId ? { cursor: 'pointer', background: '#f8fafc' } : undefined)}
                        title={editMode && isEmpty && selectedSessionId ? 'Tap to set move target' : undefined}
                        role={editMode && isEmpty && selectedSessionId ? 'button' : undefined}
                        tabIndex={editMode && isEmpty && selectedSessionId ? 0 : undefined}
                        aria-label={editMode && isEmpty && selectedSessionId ? `Move selected class to ${day} ${slot.label}` : undefined}
                        onKeyDown={event => {
                          if (editMode && isEmpty && selectedSessionId && (event.key === 'Enter' || event.key === ' ')) {
                            event.preventDefault();
                            handleSelectForMove(day, slot.idx);
                          }
                        }}
                      >
                        {cellSessions.length > 0 && <div className="tt-cell-stack">
                        {cellSessions.map((s) => {
                          const course = courses[s.course_id];
                          const electiveSectionNames = course?.program_elective_group_id == null ? [] : [...new Set(
                            allSessions
                              .filter(session => session.day === s.day && Number(session.timeslot_id) === Number(s.timeslot_id)
                                && courses[session.course_id]?.program_elective_group_id === course.program_elective_group_id)
                              .map(session => sections[session.section_id])
                              .filter(Boolean),
                          )];
                          const isSelected = editMode && selectedSessionId === s.id;
                          const isSwapPick = editMode && swapPick === s.id;
                          const facultyIds = s.teacher_ids?.length
                            ? s.teacher_ids
                            : (course?.teacher_ids?.length ? course.teacher_ids : [s.teacher_id]);
                          const facultyNames = [...new Set(facultyIds.map(id => teachers[id] || `T${id}`))].join(', ');
                          return (
                          <div
                            key={s.id}
                            onClick={() => !s.isContinuation && handleSelectSession(s)}
                            className={`tt-cell ${course?.course_type || 'lecture'} ${s.isContinuation ? 'tt-cell-continuation' : ''} ${isSelected ? 'tt-selected' : ''} ${isSwapPick ? 'tt-swap-pick' : ''}`}
                            style={editMode ? { cursor: 'pointer', ...(isSelected ? { outline: '2px solid var(--blue-700)', outlineOffset: '1px' } : {}), ...(isSwapPick ? { outline: '2px solid var(--gold-600)', outlineOffset: '1px' } : {}) } : undefined}
                            role={editMode && !s.isContinuation ? 'button' : undefined}
                            tabIndex={editMode && !s.isContinuation ? 0 : undefined}
                            aria-pressed={editMode && !s.isContinuation ? isSelected || isSwapPick : undefined}
                            aria-label={editMode && !s.isContinuation ? `${courses[s.course_id]?.course_code || 'Class'}, ${sections[s.section_id] || 'section'}, ${s.day}. Select for ${editAction}.` : undefined}
                            onKeyDown={event => {
                              if (editMode && !s.isContinuation && (event.key === 'Enter' || event.key === ' ')) {
                                event.preventDefault();
                                handleSelectSession(s);
                              }
                            }}
                          >
                            <div className="course">{course?.course_code || `Course #${s.course_id}`}{s.isContinuation ? ' · continued' : ''}</div>
                            <div className="course-name">{course?.course_name || 'Course details loading…'}</div>
                            {electiveSectionNames.length > 1 && <div className="info">Sections together: {electiveSectionNames.join(', ')}</div>}
                            {s.batch_label && <div className="tt-batch-label">{s.batch_label}</div>}
                            <div className="info">{facultyNames}</div>
                            <div className="info">{rooms[s.room_id] || `R${s.room_id}`}</div>
                            {course?.duration > 1 && <div className="info duration">Two consecutive periods</div>}
                            {editMode && <div className="info" style={{ marginTop: '4px', fontWeight: 700, color: isSelected ? 'var(--blue-700)' : isSwapPick ? 'var(--gold-600)' : 'var(--text-muted)' }}>{isSelected ? 'Selected' : isSwapPick ? 'Swap with' : 'Tap to select'}</div>}
                          </div>
                          );
                        })}
                        </div>}
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
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {!loading && entityId && sessions.length === 0 && (
        <div className="alert alert-info">No timetable data found. Generate a timetable first.</div>
      )}
      {!loading && !entityId && (
        <div className="alert alert-info">Pick a {viewType} above to view its timetable. Coordinators can use <strong>Edit timetable</strong> to make a last-minute move or swap, review the rule check, and save the change.</div>
      )}
    </div>
  );
}
