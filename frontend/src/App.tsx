import { Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import UploadPage from './pages/UploadPage';
import JDPage from './pages/JDPage';
import ResumesPage from './pages/ResumesPage';
import ResumeDetailPage from './pages/ResumeDetailPage';

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/jd" element={<JDPage />} />
          <Route path="/resumes" element={<ResumesPage />} />
          <Route path="/resumes/:id" element={<ResumeDetailPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
