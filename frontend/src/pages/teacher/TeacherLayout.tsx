import { Outlet } from "react-router";
import TeacherNav from "./TeacherNav";

/** Teacher workspace shell: sidebar (tabs on small screens) beside the active teacher page. */
export default function TeacherLayout() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 md:py-10 grid grid-cols-1 lg:grid-cols-[220px_minmax(0,1fr)] gap-6 lg:gap-10">
      <aside>
        <TeacherNav />
      </aside>
      <div className="min-w-0 space-y-6">
        <Outlet />
      </div>
    </div>
  );
}
