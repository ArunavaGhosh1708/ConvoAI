import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { AdminPage } from './pages/AdminPage'
import { ChatPage } from './pages/ChatPage'

export default function App() {
  return (
    <BrowserRouter>
      {/* Tiny dev nav — remove in production widget embed */}
      <nav className="fixed left-0 right-0 top-0 z-50 flex justify-end gap-4 bg-white/80 px-6 py-2 text-xs backdrop-blur border-b border-gray-100">
        <Link to="/"      className="text-gray-500 hover:text-brand-600 transition">Chat</Link>
        <Link to="/admin" className="text-gray-500 hover:text-brand-600 transition">Admin</Link>
      </nav>

      <div className="pt-9">
        <Routes>
          <Route path="/"      element={<ChatPage />} />
          <Route path="/admin" element={<AdminPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
