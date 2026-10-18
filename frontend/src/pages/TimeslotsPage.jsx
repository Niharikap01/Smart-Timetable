import { useState, useEffect } from 'react';
import { getTimeslots } from '../services/api';
import CrudTable from '../components/CrudTable';
import DataImportPanel from '../components/DataImportPanel';

const MASTER_SLOTS = [
  ['08:00', '09:00'], ['09:00', '10:00'], ['10:00', '11:00'],
  ['11:00', '12:00'], ['12:00', '13:00'], ['13:00', '14:00'],
  ['14:00', '15:00'], ['15:00', '16:00'], ['16:00', '17:00'],
  ['17:00', '18:00'],
];

export default function TimeslotsPage() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = () => { setLoading(true); getTimeslots().then(r => { setData(r.data); setLoading(false); }); };
  useEffect(load, []);

  const columns = [
    { key: 'day', label: 'Day' },
    { key: 'slot_index', label: 'Slot' },
    { key: 'start_time', label: 'Start' },
    { key: 'end_time', label: 'End' },
    { key: 'is_reserved', label: 'Reserved', render: (v) => v ? 'Yes' : 'No' },
    { key: 'reservation_reason', label: 'Reason' },
  ];

  return (
    <div>
      <div className="page-header">
        <h1>Timeslots</h1>
        <DataImportPanel entity="timeslots" onImported={load}
          headings={['day', 'slot_index', 'start_time', 'end_time', 'is_reserved', 'reservation_reason']}
          sampleRow={['Monday', '0', '09:00', '10:00', 'No', '']} />
      </div>
      <p>Master schedule periods: six working days × ten fixed one-hour slots, from 08:00 to 18:00. Reserved periods show MDM and recess directly in the timetable.</p>
      <CrudTable columns={columns} data={data} loading={loading} />
      <h2>Required master pattern</h2>
      <CrudTable columns={[{ key: 'slot_index', label: 'Slot' }, { key: 'start_time', label: 'Start' }, { key: 'end_time', label: 'End' }]} data={MASTER_SLOTS.map(([start_time, end_time], slot_index) => ({ slot_index, start_time, end_time }))} />
    </div>
  );
}
