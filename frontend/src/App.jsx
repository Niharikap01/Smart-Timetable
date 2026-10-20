import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
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

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
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
          <Route path="*" element={<Navigate to="/" />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
