import axios from 'axios';

const api = axios.create({
  // The active local FastAPI service uses port 8000. Deployments can override
  // this through VITE_API_URL without changing the application source.
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token');
    }
    return Promise.reject(err);
  }
);

// Auth
export const login = (username, password) =>
  api.post('/api/auth/login', new URLSearchParams({ username, password }));
export const register = (data) => api.post('/api/auth/register', data);
export const getConstraintConfig = () => api.get('/api/constraints/config');
export const updateConstraintConfig = (data) => api.put('/api/constraints/config', data);

// Teachers
export const getTeachers = (params) => api.get('/api/teachers', { params });
export const getTeacher = (id) => api.get(`/api/teachers/${id}`);
export const createTeacher = (data) => api.post('/api/teachers', data);
export const updateTeacher = (id, data) => api.put(`/api/teachers/${id}`, data);
export const deleteTeacher = (id) => api.delete(`/api/teachers/${id}`);

// Master data imports
export const importRecords = (entity, file) => {
  const data = new FormData();
  data.append('file', file);
  return api.post(`/api/import/${entity}`, data);
};

export const estimateSectionStrengths = () => api.post('/api/import/estimate-section-strengths');

// Sections
export const getSections = (params) => api.get('/api/sections', { params });
export const createSection = (data) => api.post('/api/sections', data);
export const updateSection = (id, data) => api.put(`/api/sections/${id}`, data);
export const deleteSection = (id) => api.delete(`/api/sections/${id}`);

// Courses
export const getCourses = (params) => api.get('/api/courses', { params });
export const createCourse = (data) => api.post('/api/courses', data);
export const updateCourse = (id, data) => api.put(`/api/courses/${id}`, data);
export const deleteCourse = (id) => api.delete(`/api/courses/${id}`);

// Rooms
export const getRooms = (params) => api.get('/api/rooms', { params });
export const createRoom = (data) => api.post('/api/rooms', data);
export const updateRoom = (id, data) => api.put(`/api/rooms/${id}`, data);
export const deleteRoom = (id) => api.delete(`/api/rooms/${id}`);

// Timeslots
export const getTimeslots = (params) => api.get('/api/timeslots', { params });
export const createTimeslot = (data) => api.post('/api/timeslots', data);
export const deleteTimeslot = (id) => api.delete(`/api/timeslots/${id}`);

// Availability
export const getTeacherAvailability = (teacherId) => api.get(`/api/availability/teacher/${teacherId}`);
export const createAvailability = (data) => api.post('/api/availability', data);
export const deleteAvailability = (id) => api.delete(`/api/availability/${id}`);

// Reserved Slots
export const getReservedSlots = () => api.get('/api/reserved-slots');
export const createReservedSlot = (data) => api.post('/api/reserved-slots', data);
export const deleteReservedSlot = (id) => api.delete(`/api/reserved-slots/${id}`);

// Timetable
export const getSchedules = () => api.get('/api/timetable');
export const getSchedule = (id) => api.get(`/api/timetable/${id}`);
export const generateTimetable = (data) => api.post('/api/timetable/generate', data);
export const getSectionTimetable = (id) => api.get(`/api/timetable/section/${id}`);
export const getTeacherTimetable = (id) => api.get(`/api/timetable/teacher/${id}`);
export const getRoomTimetable = (id) => api.get(`/api/timetable/room/${id}`);
export const getLatestTimetableSessions = () => api.get('/api/timetable/latest/sessions');
export const previewMove = (data) => api.post('/api/timetable/latest/preview-move', data);
export const applyMove = (data) => api.post('/api/timetable/latest/move', data);
export const previewSwap = (data) => api.post('/api/timetable/latest/preview-swap', data);
export const applySwap = (data) => api.post('/api/timetable/latest/swap', data);
export const getLatestScheduleId = () => api.get('/api/timetable/latest/id');

// Vacancy
export const getVacancyRooms = () => api.get('/api/vacancy/rooms');
export const getVacancySummary = () => api.get('/api/vacancy/summary');
export const getVacancyRoom = (id) => api.get(`/api/vacancy/${id}`);

// Health
export const healthCheck = () => api.get('/api/health');

export default api;
