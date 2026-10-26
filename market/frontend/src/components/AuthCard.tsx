import type { ReactNode } from "react";

export default function AuthCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <div className="card w-full max-w-md">
        <div className="flex flex-col gap-1">
          <p className="text-sm font-medium text-indigo-600">Apply Desk</p>
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        </div>
        {children}
      </div>
    </div>
  );
}
