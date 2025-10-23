import React, { useState } from 'react';
import CRSInfoPage from './pages/CRSInfoPage';
import TransformPage from './pages/TransformPage';
import CustomCRSPage from './pages/CustomCRSPage';
import LocalOffsetPage from './pages/LocalOffsetPage';
import ViaTransformPage from './pages/ViaTransformPage';
import DocsPage from './pages/DocsPage';
import GigsReportsPage from './pages/GigsReportsPage';

export default function App() {
  const [page, setPage] = useState('crs');

  React.useEffect(() => {
    const fromHash = (hash) => {
      const h = (hash || '').replace('#', '');
      if (['crs','transform','via','custom','local','gigs','docs'].includes(h)) return h;
      return null;
    };
    const initial = fromHash(window.location.hash);
    if (initial) setPage(initial);
    const onHash = () => {
      const p = fromHash(window.location.hash);
      if (p) setPage(p);
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const setPageAndHash = (key) => {
    setPage(key);
    window.location.hash = `#${key}`;
  };

  const navBtn = (key, label) => (
    <button
      className={`btn ${page===key ? 'btn-primary' : ''}`}
      onClick={() => setPageAndHash(key)}
      disabled={page===key}
    >{label}</button>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white">
        <div className="mx-auto max-w-6xl px-4 py-4 flex items-center justify-between">
          <h1 className="text-xl font-semibold text-gray-800">CRS Transformation Platform</h1>
          <nav className="flex gap-2">
            {navBtn('crs','CRS Info')}
            {navBtn('transform','Transform')}
            {navBtn('via','Transform Via')}
            {navBtn('custom','Custom CRS')}
            {navBtn('local','Local Offset')}
            {navBtn('gigs','GIGS Reports')}
            {navBtn('docs','Docs')}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        {page === 'crs' && <div className="card"><div className="card-body"><CRSInfoPage /></div></div>}
        {page === 'transform' && <div className="card"><div className="card-body"><TransformPage /></div></div>}
        {page === 'via' && <div className="card"><div className="card-body"><ViaTransformPage /></div></div>}
        {page === 'custom' && <div className="card"><div className="card-body"><CustomCRSPage /></div></div>}
        {page === 'local' && <div className="card"><div className="card-body"><LocalOffsetPage /></div></div>}
        {page === 'gigs' && <div className="card"><div className="card-body"><GigsReportsPage /></div></div>}
        {page === 'docs' && <div className="card"><div className="card-body"><DocsPage /></div></div>}
      </main>
    </div>
  );
}
