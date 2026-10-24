import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import { getCurrentUser } from './services/api';
import Layout from './layouts/Layout';
import Dashboard from './pages/Dashboard';
import TeachersPage from './pages/TeachersPage';
import SectionsPage from './pages/SectionsPage';
import CoursesPage from './pages/CoursesPage';
import RoomsPage from './pages/RoomsPage';
import TimeslotsPage from './pages/TimeslotsPage';
import GeneratePage from './pages/GeneratePage';
import TimetablePage from './pages/TimetablePage';
import VacancyPage from './pages/VacancyPage';
import LoginPage from './pages/LoginPage';
import ConstraintsPage from './pages/ConstraintsPage';
import ProgramElectivesPage from './pages/ProgramElectivesPage';

function RequireLogin() {
  const location = useLocation();
  const [authState, setAuthState] = useState(() => (
    localStorage.getItem('token') ? 'checking' : 'signed-out'
  ));

  useEffect(() => {
    if (!localStorage.getItem('token')) {
      setAuthState('signed-out');
      return undefined;
    }

    let active = true;
    getCurrentUser()
      .then(() => { if (active) setAuthState('signed-in'); })
      .catch(() => { if (active) setAuthState('signed-out'); });
    return () => { active = false; };
  }, []);

  if (authState === 'checking') {
    return <div className="login-page"><div className="card login-card">Checking sign-in…</div></div>;
  }
  if (authState !== 'signed-in') {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <Outlet />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireLogin />}>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="teachers" element={<TeachersPage />} />
            <Route path="sections" element={<SectionsPage />} />
            <Route path="courses" element={<CoursesPage />} />
            <Route path="program-electives" element={<ProgramElectivesPage />} />
            <Route path="rooms" element={<RoomsPage />} />
            <Route path="timeslots" element={<TimeslotsPage />} />
            <Route path="constraints" element={<ConstraintsPage />} />
            <Route path="generate" element={<GeneratePage />} />
            <Route path="timetable" element={<TimetablePage />} />
            <Route path="vacancy" element={<VacancyPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
