import { Navigate, Route, Routes } from 'react-router-dom';
import { Admin } from './admin/Admin';
import { Display } from './display/Display';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Display />} />
      <Route path="/display" element={<Display />} />
      <Route path="/admin" element={<Admin />} />
      <Route path="*" element={<Navigate to="/display" replace />} />
    </Routes>
  );
}
