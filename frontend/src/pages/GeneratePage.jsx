import { useState, useEffect } from 'react';
import { generateTimetable, getSections, getCourses, getRooms, getTimeslots, getConstraintConfig } from '../services/api';

export default function GeneratePage() {
  const [stats, setStats] = useState({});
  const [scopeTotals, setScopeTotals] = useState({ sections: 0, courses: 0 });
  const [timeout, setTimeout_] = useState(30);
  const [optimization, setOptimization] = useState(true);
  const [semester, setSemester] = useState('5');
  const [generating, setGenerating] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [constraintProfile, setConstraintProfile] = useState(null);
  const [preflight, setPreflight] = useState({ missingAssignments: [], unknownStrengths: [], unknownCapacities: [], missingResources: [] });
  const hasPreflightIssues = preflight.missingAssignments.length > 0
    || preflight.unknownStrengths.length > 0
    || preflight.unknownCapacities.length > 0
    || preflight.missingResources.length > 0;

  useEffect(() => {
    Promise.all([
      getSections().then(r => r.data),
      getCourses().then(r => r.data),
      getRooms().then(r => r.data),
      getTimeslots().then(r => r.data),
    ]).then(([sections, courses, rooms, timeslots]) => {
      const cseSections = sections.filter(s => s.program?.toUpperCase() === 'CSE');
      const cseSectionIds = new Set(cseSections.map(s => s.id));
      const allActiveCourses = courses.filter(c => c.active && cseSectionIds.has(c.section_id));
      const selectedSections = semester === 'all'
        ? cseSections
        : cseSections.filter(s => s.semester === Number(semester));
      const activeCourses = courses.filter(c => c.active && selectedSections.some(s => s.id === c.section_id));
      const totalSessions = activeCourses.reduce((s, c) => s + c.weekly_sessions, 0);
      setStats({ sections: selectedSections.length, courses: activeCourses.length, sessions: totalSessions, rooms: rooms.length, timeslots: timeslots.length });
      setScopeTotals({ sections: cseSections.length, courses: allActiveCourses.length });
      setPreflight({
        missingAssignments: selectedSections.filter(s => !activeCourses.some(c => c.section_id === s.id)).map(s => s.name),
        unknownStrengths: selectedSections.filter(s => s.strength <= 0).map(s => s.name),
        unknownCapacities: rooms.filter(r => r.capacity <= 0).map(r => r.room_number),
        missingResources: [
          ...(rooms.length === 0 ? ['Add lecture rooms and laboratories with capacities.'] : []),
          ...(timeslots.length === 0 ? ['Add the six-day master timeslot pattern.'] : []),
        ],
      });
    });
  }, [semester]);

  useEffect(() => {
    getConstraintConfig()
      .then(response => setConstraintProfile(response.data))
      .catch(() => setConstraintProfile(null));
  }, []);

  useEffect(() => {
    if (!generating) return;
    const t = setInterval(() => setElapsed(e => e + 1), 1000);
    return () => clearInterval(t);
  }, [generating]);

  const handleGenerate = async () => {
    setGenerating(true); setElapsed(0); setResult(null); setError('');
    try {
      const res = await generateTimetable({
        timeout_seconds: timeout,
        enable_optimization: optimization,
        semester: semester === 'all' ? null : Number(semester),
      });
      setResult(res.data);
    } catch (e) {
      setError(e.response?.data?.detail || 'Generation failed');
    }
    setGenerating(false);
  };

  const semesterName = { 1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V', 6: 'VI', 7: 'VII', 8: 'VIII' }[semester];

  return (
    <div>
      <div className="page-header"><h1>Generate Timetable</h1></div>

      <div className="stats-grid">
        <div className="stat-card"><div className="label">Sections</div><div className="value">{stats.sections ?? '—'}</div></div>
        <div className="stat-card"><div className="label">Courses</div><div className="value">{stats.courses ?? '—'}</div></div>
        <div className="stat-card"><div className="label">Sessions</div><div className="value">{stats.sessions ?? '—'}</div></div>
        <div className="stat-card"><div className="label">Rooms</div><div className="value">{stats.rooms ?? '—'}</div></div>
        <div className="stat-card"><div className="label">Timeslots</div><div className="value">{stats.timeslots ?? '—'}</div></div>
      </div>
      <p className="form-hint" style={{ margin: '-0.75rem 0 1.5rem' }}>
        {semester === 'all'
          ? `Counts include all imported CSE semesters: ${scopeTotals.sections} active sections and ${scopeTotals.courses} active courses.`
          : `Counts above are for Semester ${semesterName} only. Across all imported CSE semesters: ${scopeTotals.sections} active sections and ${scopeTotals.courses} active courses.`}
      </p>

      {hasPreflightIssues && (
        <div className="alert alert-info" style={{ marginBottom: '1.5rem' }}>
          <strong>Generation preflight</strong>
          {preflight.missingAssignments.length > 0 && <p>Missing course/faculty assignments: {preflight.missingAssignments.join(', ')}.</p>}
          {preflight.unknownStrengths.length > 0 && <p>Section strengths not configured: {preflight.unknownStrengths.join(', ')}.</p>}
          {preflight.unknownCapacities.length > 0 && <p>Room capacities not configured: {preflight.unknownCapacities.join(', ')}.</p>}
          {preflight.missingResources.map(issue => <p key={issue}>{issue}</p>)}
          <p>Enter verified data before generating. The system intentionally will not invent it.</p>
        </div>
      )}

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <h3 style={{ marginBottom: '1rem' }}>Configuration</h3>
        <div className="form-grid">
          <div className="form-group"><label>Scheduling scope</label>
            <select value={semester} onChange={e => setSemester(e.target.value)}>
              <option value="5">Semester V — ready for mapping review</option>
              <option value="3">Semester III — ready for mapping review</option>
              <option value="1">Semester I — coordinator mapping required</option>
              <option value="7">Semester VII — coordinator mapping required</option>
              <option value="all">All imported semesters</option>
            </select>
            <span className="form-hint">Start with Semester V or III. Incomplete semesters stay stored but do not block this selected timetable.</span>
          </div>
          <div className="form-group"><label>Algorithm</label><input value="Google OR-Tools CP-SAT (with CSP fallback)" disabled /></div>
          <div className="form-group"><label>Timeout (seconds)</label><input type="number" value={timeout} onChange={e => setTimeout_(parseInt(e.target.value))} /></div>
          <div className="form-group"><label>Academic balance</label>
            <select value={optimization} onChange={e => setOptimization(e.target.value === 'true')}>
              <option value="true">Balanced week (recommended)</option><option value="false">Basic feasibility only</option>
            </select></div>
        </div>
        <button className="btn btn-primary" onClick={handleGenerate} disabled={generating || hasPreflightIssues} style={{ marginTop: '1rem', fontSize: '1rem', padding: '0.75rem 2rem' }}>
          {generating ? `Generating... (${elapsed}s)` : hasPreflightIssues ? 'COMPLETE PREFLIGHT DATA FIRST' : 'GENERATE TIMETABLE'}
        </button>
      </div>

      <div className="card planning-guide" style={{ marginBottom: '1.5rem' }}>
        <h3>How optimisation works</h3>
        <p><strong>Keep “Balanced week” selected.</strong> Google CP-SAT searches for a valid timetable while preferring a wider weekly spread, separate course days, and better-fitting rooms.</p>
        <p>The non-negotiable rules still apply in both modes: room/faculty conflicts, the course credit count, recess/lunch blocks, and no unnecessary student gaps. The latest first-class start time follows the active coordinator constraint profile{constraintProfile ? ` (${constraintProfile.config.LATEST_SECTION_START_TIME})` : ''}.</p>
        {constraintProfile && <p>Active constraint profile v{constraintProfile.version}: section daily limit {constraintProfile.config.MAX_SECTION_DAILY_HOURS}, lecture daily limit {constraintProfile.config.MAX_LECTURE_PERIODS_PER_DAY}, consecutive-period limit {constraintProfile.config.MAX_CONSECUTIVE_PERIODS}, and teacher daily limit {constraintProfile.config.MAX_TEACHER_DAILY_HOURS}.</p>}
        <p>For a large real-college import, leave the timeout at 30 seconds initially. Increase it to 60–90 seconds only if the result reports a timeout or a real resource bottleneck.</p>
      </div>

      {generating && (
        <div className="card">
          <div className="loading">
            <div className="spinner" style={{ marginBottom: '1rem' }} />
            <p>Generating timetable... {elapsed}s elapsed</p>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Google OR-Tools CP-SAT · CSP Backtracking fallback available</p>
          </div>
        </div>
      )}

      {error && <div className="alert alert-error">{error}</div>}

      {result && (
        <div className={`card ${result.status === 'VALID' ? '' : ''}`} style={{ borderLeft: `4px solid ${result.status === 'VALID' ? 'var(--success)' : 'var(--danger)'}` }}>
          <h3 style={{ marginBottom: '1rem' }}>{result.status === 'VALID' ? '✓ Timetable Generated Successfully' : '✗ Generation Failed'}</h3>
          {result.message && <div className="alert alert-error" style={{ marginBottom: '1rem' }}>{result.message}</div>}
          <div className="stats-grid" style={{ marginBottom: '0' }}>
            <div><strong>Status:</strong> <span className={`badge ${result.status === 'VALID' ? 'badge-free' : 'badge-occupied'}`}>{result.status}</span></div>
            <div><strong>Hard Violations:</strong> {result.hard_constraint_violations}</div>
            <div><strong>Soft Score:</strong> {result.soft_constraint_score?.toFixed(1) ?? '—'}</div>
            <div><strong>Generation Time:</strong> {result.generation_time_ms}ms</div>
            <div><strong>Sessions:</strong> {result.sessions_scheduled}/{result.sessions_expected}</div>
            <div><strong>Backtracks:</strong> {result.backtracks}</div>
            <div><strong>Restarts:</strong> {result.restarts}</div>
            <div><strong>Algorithm:</strong> {result.algorithm}</div>
          </div>
          {result.unscheduled_sessions?.length > 0 && (
            <div style={{ marginTop: '1rem' }}>
              <strong>Unscheduled:</strong>
              <ul>{result.unscheduled_sessions.map((s, i) => <li key={i}>{s}</li>)}</ul>
            </div>
          )}
          {result.bottlenecks?.length > 0 && (
            <div style={{ marginTop: '0.5rem' }}>
              <strong>Bottlenecks:</strong>
              <ul>{result.bottlenecks.map((b, i) => <li key={i}>{b}</li>)}</ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
