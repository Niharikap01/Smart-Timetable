export default function CrudTable({ columns, data, onEdit, onDelete, loading }) {
  if (loading) return <div className="loading"><div className="spinner" /></div>;
  if (!data?.length) return <div className="alert alert-info">No records found.</div>;
  const hasActions = Boolean(onEdit || onDelete);

  return (
    <div className="card" style={{ overflowX: 'auto' }}>
      <table>
        <thead>
          <tr>
            {columns.map((c) => <th key={c.key}>{c.label}</th>)}
            {hasActions && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr key={row.id}>
              {columns.map((c) => (
                <td key={c.key}>{c.render ? c.render(row[c.key], row) : String(row[c.key] ?? '')}</td>
              ))}
              {hasActions && <td>
                {onEdit && <button className="btn btn-secondary btn-sm" onClick={() => onEdit(row)}>Edit</button>}
                {' '}
                {onDelete && <button className="btn btn-danger btn-sm" onClick={() => onDelete(row.id)}>Delete</button>}
              </td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
