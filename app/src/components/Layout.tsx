import type { ReactNode } from 'react';
import Sidebar from './Sidebar';
import TopBar from './TopBar';

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen w-screen" style={{ backgroundColor: 'var(--bg-base)' }}>
      <Sidebar />
      <div className="ml-[220px] flex flex-1 flex-col overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
