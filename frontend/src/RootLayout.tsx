import { Outlet } from "react-router";
import { ThemeProvider } from "@/components/ThemeProvider";
import Navbar from "@/components/Navbar";

/** App shell for every route: theme, top navigation, and the active page. */
export default function RootLayout() {
  return (
    <ThemeProvider>
      <Navbar />
      <main className="flex-1">
        <Outlet />
      </main>
    </ThemeProvider>
  );
}
