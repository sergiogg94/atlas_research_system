import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Layout } from "./components/Layout";
import { LoadingSpinner } from "./components/LoadingSpinner";
import './App.css'
import './styles.css'
import { ToastProvider } from "./components/ToastProvider";

const HomePage = lazy(() => import("./pages/HomePage"));
const TaskListPage = lazy(() => import("./pages/TaskListPage"));
const TaskDetailPage = lazy(() => import("./pages/TaskDetailPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));

function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <Layout>
          <Suspense fallback={<LoadingSpinner />}>
            <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/tasks" element={<TaskListPage />} />
            <Route path="/tasks/:traceId" element={<TaskDetailPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
          </Suspense>
        </Layout>
      </ToastProvider>
    </BrowserRouter>
  );
}

export default App
