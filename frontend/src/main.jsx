import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

// Require a fresh sign-in whenever the application is opened; keep the token
// only for navigation within this running app session.
localStorage.removeItem('token');

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
