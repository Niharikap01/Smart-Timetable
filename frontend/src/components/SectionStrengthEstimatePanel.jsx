import { useState } from 'react';
import { estimateSectionStrengths } from '../services/api';

export default function SectionStrengthEstimatePanel({ onUpdated }) {
  const [estimating, setEstimating] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const applyEstimate = async () => {
    setEstimating(true);
    setError('');
    setResult(null);
    try {
      const response = await estimateSectionStrengths();
      setResult(response.data);
      await onUpdated?.();
    } catch (requestError) {
      const detail = requestError.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Could not apply the planning strength estimate.');
    } finally {
      setEstimating(false);
    }
  };

  return (
    <section className="strength-estimate-panel" aria-label="Planning strength estimate">
      <div>
        <strong>Planning strength estimate</strong>
        <p>Apply the approved 60–65 student estimate across all CSE sections. Replace it with official enrolment when available.</p>
      </div>
      <button type="button" className="btn btn-secondary" disabled={estimating} onClick={applyEstimate}>
        {estimating ? 'Applying strengths…' : 'Apply 60–65 estimates'}
      </button>
      {error && <div className="import-status error">{error}</div>}
      {result && <div className="import-status success">{result.message} {result.updated} sections updated.</div>}
    </section>
  );
}
