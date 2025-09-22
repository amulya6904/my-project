import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import SimpleApp from './SimpleApp';
import ReportPage from './pages/ReportPage';

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<SimpleApp />} />
        <Route path="/report" element={<ReportPage />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
