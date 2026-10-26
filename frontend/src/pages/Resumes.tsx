import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "../components/PageHeader";
import ResumePreview from "../components/ResumePreview";
import { api } from "../api";
import type { GeneratedResume, Region, ResumePdf, ResumeRegion } from "../types";

export default function Resumes() {
  const [region, setRegion] = useState<Region>("INR");
  const [data, setData] = useState<ResumeRegion[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [overwrite, setOverwrite] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<GeneratedResume | null>(null);
  const [preview, setPreview] = useState<ResumePdf | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

  const load = () => {
    api
      .resumes(region)
      .then((payload) => setData(payload.regions))
      .catch((err: Error) => setError(err.message));
  };

  useEffect(() => {
    setSelected([]);
    setPendingDelete(null);
    load();
  }, [region]);

  const onGenerate = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const generated = await api.generateResume({
        company,
        role,
        region,
        job_description: jobDescription,
        overwrite,
        source_paths: selected,
      });
      setResult(generated);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generate failed");
    } finally {
      setBusy(false);
    }
  };

  const toggleSelected = (path: string) => {
    setSelected((current) => (current.includes(path) ? current.filter((item) => item !== path) : [...current, path]));
  };

  const onDelete = async (pdf: ResumePdf) => {
    setBusy(true);
    setError(null);
    try {
      await api.deleteResume(pdf.path);
      setSelected((current) => current.filter((item) => item !== pdf.path));
      setPendingDelete(null);
      if (preview?.path === pdf.path) setPreview(null);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  };

  const current = data.find((item) => item.region === region);

  return (
    <div className="page">
      <PageHeader
        title="Resumes"
        description="Browse stock CVs and generate a tailored PDF from your profile."
        actions={
          <div className="flex gap-2">
            {(["INR", "UAE"] as Region[]).map((value) => (
              <button key={value} type="button" onClick={() => setRegion(value)} className={region === value ? "btn-primary" : "btn-secondary"}>
                {value}
              </button>
            ))}
          </div>
        }
      />

      {error && <p className="rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
      {result && (
        <p className="rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          {result.existed ? "Already existed: " : "Generated: "}
          {result.path}
          {result.markdown_only ? " (Markdown only — WeasyPrint unavailable)" : ""}
        </p>
      )}

      <form onSubmit={onGenerate} className="card">
        <div className="flex flex-col gap-1">
          <h2 className="font-semibold">Generate tailored PDF</h2>
          <p className="text-sm text-slate-500">
            Tick one or more resumes below. Their jobs, projects, and skills are combined, then shaped for this role. Leave them unticked to use your full{" "}
            <Link className="font-medium text-indigo-600" to="/profile">Profile</Link>.
          </p>
          {selected.length > 0 && (
            <p className="text-sm font-medium text-indigo-700">
              Combining {selected.length} {selected.length === 1 ? "resume" : "resumes"}.
            </p>
          )}
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <input required value={company} onChange={(event) => setCompany(event.target.value)} placeholder="Company" className="field" />
          <input required value={role} onChange={(event) => setRole(event.target.value)} placeholder="Role" className="field" />
        </div>
        <textarea
          value={jobDescription}
          onChange={(event) => setJobDescription(event.target.value)}
          placeholder="Job description"
          rows={5}
          className="field"
        />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={overwrite} onChange={(event) => setOverwrite(event.target.checked)} />
          Overwrite if a generated PDF already exists
        </label>
        <button type="submit" disabled={busy} className="btn-primary self-start">
          {busy ? "Generating…" : "Generate resume"}
        </button>
      </form>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {current?.folders.map((folder) => (
          <article key={folder.name} className="card">
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-semibold">{folder.name}</h2>
              <div className="flex items-center gap-2">
                {folder.pdfs.length > 0 && (
                  <button
                    type="button"
                    className="text-sm font-medium text-indigo-600"
                    onClick={() =>
                      setSelected((current) => [...new Set([...current, ...folder.pdfs.map((pdf) => pdf.path)])])
                    }
                  >
                    Select all
                  </button>
                )}
                {folder.generated && <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700">Generated</span>}
              </div>
            </div>
            {folder.pdfs.length === 0 && <p className="text-sm text-slate-500">No PDFs in this folder.</p>}
            {folder.pdfs.map((pdf) => (
              <div key={pdf.path} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={selected.includes(pdf.path)}
                  onChange={() => toggleSelected(pdf.path)}
                  aria-label={`Include ${pdf.filename}`}
                />
                <button
                  type="button"
                  onClick={() => setPreview(pdf)}
                  className="flex min-w-0 flex-1 items-center justify-between gap-3 rounded-lg px-2 py-2 text-left text-sm hover:bg-slate-50"
                >
                  <span className="truncate font-medium">{pdf.filename}</span>
                  <span className="shrink-0 text-indigo-600">Preview</span>
                </button>
                {pendingDelete === pdf.path ? (
                  <div className="flex shrink-0 gap-2">
                    <button type="button" className="btn-danger" disabled={busy} onClick={() => onDelete(pdf)}>
                      Delete
                    </button>
                    <button type="button" className="btn-secondary" onClick={() => setPendingDelete(null)}>
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button type="button" className="btn-secondary shrink-0" onClick={() => setPendingDelete(pdf.path)}>
                    Delete
                  </button>
                )}
              </div>
            ))}
          </article>
        ))}
      </div>
      {preview && <ResumePreview path={preview.path} filename={preview.filename} onClose={() => setPreview(null)} />}
    </div>
  );
}
