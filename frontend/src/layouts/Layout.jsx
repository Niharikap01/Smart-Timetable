import { Outlet, NavLink } from 'react-router-dom';

const links = [
  { to: '/', label: 'Dashboard', code: 'DB' },
  { to: '/teachers', label: 'Faculty', code: 'FC' },
  { to: '/sections', label: 'Sections', code: 'SC' },
  { to: '/courses', label: 'Courses', code: 'CR' },
  { to: '/rooms', label: 'Rooms', code: 'RM' },
  { to: '/timeslots', label: 'Timeslots', code: 'TS' },
  { to: '/constraints', label: 'Constraints', code: 'CX' },
  { to: '/generate', label: 'Generate', code: 'GN' },
  { to: '/timetable', label: 'Timetable', code: 'TT' },
  { to: '/vacancy', label: 'Vacancy', code: 'VC' },
];

export default function Layout() {
  return (
    <div className="app-layout">
      <nav className="sidebar">
        <div className="sidebar-header">
          <div className="brand-mark" aria-hidden="true">ST</div>
          <div className="brand-copy">
            <div className="brand-title">Smart Timetable</div>
            <div className="brand-subtitle">Academic Planning</div>
          </div>
        </div>
        <div className="sidebar-section">CSE Department</div>
        {links.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.to === '/'} className={({ isActive }) => isActive ? 'active' : ''}>
            <span className="nav-code" aria-hidden="true">{l.code}</span>
            <span className="nav-label">{l.label}</span>
          </NavLink>
        ))}
      </nav>
      <main className="main-content">
        <header className="portal-bar">
          <div className="portal-context">
            <strong>Department of Computer Science &amp; Engineering</strong>
            <span className="portal-separator">/</span>
            <span className="portal-label">Academic Scheduling Portal</span>
          </div>
          <div className="portal-status">System online</div>
        </header>
        <Outlet />
      </main>
    </div>
  );
}
