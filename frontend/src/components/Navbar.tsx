import { Link, useLocation } from 'react-router-dom';
import { FileText, Briefcase, Users, User } from 'lucide-react';

export default function Navbar() {
  const location = useLocation();

  const isActive = (path: string) => location.pathname === path;

  return (
    <nav className="bg-primary shadow-lg">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center">
            <User className="h-8 w-8 text-white mr-2" />
            <span className="text-white font-bold text-xl">AI 简历筛选助手</span>
          </div>
          <div className="flex space-x-4">
            <Link
              to="/"
              className={`flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive('/')
                  ? 'bg-secondary text-white'
                  : 'text-blue-100 hover:bg-blue-800 hover:text-white'
              }`}
            >
              <FileText className="h-4 w-4 mr-2" />
              上传简历
            </Link>
            <Link
              to="/jd"
              className={`flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive('/jd')
                  ? 'bg-secondary text-white'
                  : 'text-blue-100 hover:bg-blue-800 hover:text-white'
              }`}
            >
              <Briefcase className="h-4 w-4 mr-2" />
              职位管理
            </Link>
            <Link
              to="/resumes"
              className={`flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive('/resumes')
                  ? 'bg-secondary text-white'
                  : 'text-blue-100 hover:bg-blue-800 hover:text-white'
              }`}
            >
              <Users className="h-4 w-4 mr-2" />
              简历列表
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
}
