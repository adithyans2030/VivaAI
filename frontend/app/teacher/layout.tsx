import { Suspense } from "react";
import TeacherNav from "./TeacherNav";

export default function TeacherLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 md:py-10 grid grid-cols-1 lg:grid-cols-[220px_minmax(0,1fr)] gap-6 lg:gap-10">
      <aside>
        <Suspense fallback={null}>
          <TeacherNav />
        </Suspense>
      </aside>
      <div className="min-w-0 space-y-6">{children}</div>
    </div>
  );
}
