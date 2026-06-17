import { useEffect } from 'react';
import { Routes, Route } from 'react-router-dom';
import Layout from '@/components/Layout';
import Dashboard from '@/pages/Dashboard';
import Devices from '@/pages/Devices';
import DeviceDetail from '@/pages/DeviceDetail';
import CameraMonitor from '@/pages/CameraMonitor';
import Discovery from '@/pages/Discovery';
import Activity from '@/pages/Activity';
import Settings from '@/pages/Settings';

function applyTheme(theme: 'dark' | 'light') {
  const root = document.documentElement;
  if (theme === 'light') root.classList.add('light');
  else root.classList.remove('light');
}

export default function App() {
  useEffect(() => {
    const saved = localStorage.getItem('myiot-theme') as 'dark' | 'light' | null;
    applyTheme(saved || 'dark');
  }, []);

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/devices" element={<Devices />} />
        <Route path="/devices/:id" element={<DeviceDetail />} />
        <Route path="/cameras" element={<CameraMonitor />} />
        <Route path="/discovery" element={<Discovery />} />
        <Route path="/activity" element={<Activity />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Layout>
  );
}
