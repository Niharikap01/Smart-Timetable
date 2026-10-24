import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { getConstraintConfig, updateConstraintConfig } from '../services/api';

const FIELDS = [
  { key: 'MAX_LECTURE_PERIODS_PER_DAY', code: 'C10', label: 'Lecture periods per section per day', help: 'Maximum lecture periods for one section on any day.' },
  { key: 'MAX_SECTION_DAILY_HOURS', code: 'C12', label: 'Total periods per section per day', help: 'Maximum total class periods for one section in a day.' },
  { key: 'MAX_CONSECUTIVE_PERIODS', code: 'C11', label: 'Consecutive periods', help: 'Maximum uninterrupted periods before a free or reserved break.' },
  { key: 'MAX_TEACHER_DAILY_HOURS', code: 'C17', label: 'Teaching periods per teacher per day', help: 'Maximum periods assigned to one teacher in a day.' },
];

function getErrorMessage(error) {
  const detail = error.response?.data?.detail;
  return typeof detail === 'string' ? detail : 'Could not save the constraint profile. Check the values and try again.';
}

export default function ConstraintsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [profile, setProfile] = useState(null);
  const [values, setValues] = useState({});
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [accessDenied, setAccessDenied] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await getConstraintConfig();
      setProfile(response.data);
      setValues(response.data.config);
      setAccessDenied(false);
    } catch (requestError) {
      const status = requestError.response?.status;
      if (status === 401) {
        navigate('/login', { replace: true, state: { from: location } });
        return;
      }
      setAccessDenied(status === 403);
      setError(status === 403
        ? 'This account does not have coordinator permissions. Ask an administrator to provision a coordinator account.'
        : 'Could not load the active constraint profile.');
    } finally {
      setLoading(false);
    }
  }, [location, navigate]);

  useEffect(() => { load(); }, [load]);

  const handleSave = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const response = await updateConstraintConfig({
        ...Object.fromEntries(FIELDS.map(({ key }) => [key, Number(values[key])])),
        LATEST_SECTION_START_TIME: values.LATEST_SECTION_START_TIME,
        change_reason: reason.trim(),
      });
      setProfile((current) => ({ ...current, ...response.data }));
      setValues(response.data.config);
      setReason('');
      setNotice(`Constraint profile v${response.data.version} saved. It will be used by the next timetable generation.`);
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Scheduling Constraints</h1>
          <p>Adjust supported timetable rules used during generation.</p>
        </div>
        {profile && <span className="constraint-version">Active profile v{profile.version}</span>}
      </div>

      {error && <div className="alert alert-error" role="alert">{error}</div>}
      {notice && <div className="alert alert-success" role="status">{notice}</div>}

      {accessDenied ? (
        <div className="card constraint-note">
          <h2>Coordinator access required</h2>
          <p>Constraint changes are restricted to coordinator and administrator accounts. Ask an administrator to grant coordinator access.</p>
        </div>
      ) : loading ? (
        <div className="card">Loading active constraint profile…</div>
      ) : profile && (
        <>
          <div className="card constraint-note">
            <h2>Editable scheduling rules</h2>
            <p>Values are applied during solver generation and final validation. Each save creates a version, and generated timetables retain a snapshot of the profile they used.</p>
            <p><strong>Fixed rules:</strong> room and teacher conflict prevention, room suitability and capacity, required weekly sessions, reserved periods, faculty availability, and at most one lecture for a course in a section per day remain enforced.</p>
          </div>

          <form className="card constraint-form" onSubmit={handleSave}>
            <div className="constraint-fields">
              {FIELDS.map((field) => (
                <div className="form-group" key={field.key}>
                  <label htmlFor={field.key}>{field.label} <span className="constraint-code">{field.code}</span></label>
                  <input
                    id={field.key}
                    type="number"
                    min="1"
                    max="24"
                    step="1"
                    required
                    value={values[field.key] ?? ''}
                    onChange={(event) => setValues({ ...values, [field.key]: event.target.value })}
                  />
                  <small>{field.help} Range: 1–24 periods.</small>
                </div>
              ))}
              <div className="form-group">
                <label htmlFor="LATEST_SECTION_START_TIME">Latest allowed first-class start time <span className="constraint-code">C20</span></label>
                <input
                  id="LATEST_SECTION_START_TIME"
                  type="time"
                  required
                  value={values.LATEST_SECTION_START_TIME ?? '12:00'}
                  onChange={(event) => setValues({ ...values, LATEST_SECTION_START_TIME: event.target.value })}
                />
                <small>A section’s first class of the day must begin by this time.</small>
              </div>
            </div>

            <div className="form-group constraint-reason">
              <label htmlFor="change-reason">Reason for this change</label>
              <textarea
                id="change-reason"
                rows="3"
                minLength="3"
                maxLength="500"
                required
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                placeholder="For example: Approved by the department coordinator for Semester V."
              />
            </div>

            {profile.change_reason && <p className="constraint-history">Previous update: {profile.change_reason}</p>}
            <button className="btn btn-primary" type="submit" disabled={saving}>
              {saving ? 'Saving…' : 'Save constraint profile'}
            </button>
          </form>
        </>
      )}
    </>
  );
}
