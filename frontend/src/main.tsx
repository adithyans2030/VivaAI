import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";
import "./globals.css";
import RootLayout from "./RootLayout";
import Home from "./pages/Home";
import Login from "./pages/Login";
import Student from "./pages/Student";
import DesignSystem from "./pages/DesignSystem";
import NotFound from "./pages/NotFound";
import TeacherLayout from "./pages/teacher/TeacherLayout";
import Sessions from "./pages/teacher/Sessions";
import SessionDetail from "./pages/teacher/SessionDetail";
import Materials from "./pages/teacher/Materials";
import Subjects from "./pages/teacher/Subjects";
import Analytics from "./pages/teacher/Analytics";

const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      { path: "/", element: <Home /> },
      { path: "/login", element: <Login /> },
      { path: "/student", element: <Student /> },
      { path: "/design-system", element: <DesignSystem /> },
      {
        path: "/teacher",
        element: <TeacherLayout />,
        children: [
          { index: true, element: <Sessions /> },
          { path: "sessions/:id", element: <SessionDetail /> },
          { path: "materials", element: <Materials /> },
          { path: "subjects", element: <Subjects /> },
          { path: "analytics", element: <Analytics /> },
        ],
      },
      { path: "*", element: <NotFound /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>
);
