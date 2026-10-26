import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, profileDraftKey } from "../api";
import PageHeader from "../components/PageHeader";
import type { Country, StoredResume } from "../types";

export default function Resumes() {
  const navigate = useNavigate();
  const [countries, setCountries] = useState<Country[]>([]);
  const [resumes, setResumes] = useState<StoredResume[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = () => {
    api.countries().then(setCountries).catch((err: Error) => setError(err.message));
    api.resumes().then(setResumes).catch((err: Error) => setError(err.message));
  };

  useEffect(() => {
    load();
  }, []);

  const upload = (countryId: string, file: File | undefined) => {
    if (!file) return;
    setBusyId(countryId);
    setError(null);
    setNotice(null);
    api
      .uploadCountryResume(countryId, file)
      .then(() => {
        setNotice("Resume saved. The first file in a country is the default until you change it.");
        load();
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setBusyId(null));
  };

  const fillProfile = (resume: StoredResume) => {
    setBusyId(resume.id);
    setError(null);
    api
      .fillFromResume(resume.id)
      .then((draft) => {
        sessionStorage.setItem(profileDraftKey, JSON.stringify(draft));
        navigate("/profile");
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setBusyId(null));
  };

  return (
    <div className="page">
      <PageHeader
        title="Resumes"
        description="Each country has its own files. One resume in that group is the default, and you can change which one."
      />
      {notice && <p className="text-sm text-emerald-700">{notice}</p>}
      {error && <p className="text-sm text-rose-600">{error}</p>}
      {countries.length === 0 && (
        <section className="card">
          <p className="text-sm text-slate-500">
            Add a country first. Resumes are grouped by the countries you save. <Link className="font-medium text-indigo-600" to="/countries">Open countries</Link>
          </p>
        </section>
      )}
      {countries.map((country) => {
        const files = resumes.filter((resume) => resume.country_id === country.id);
        return (
          <section key={country.id} className="card">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-col gap-1">
                <h2 className="font-semibold">{country.label}</h2>
                <p className="text-sm text-slate-500">{files.length === 0 ? "No resumes yet." : `${files.length} file${files.length === 1 ? "" : "s"}`}</p>
              </div>
              <label className="btn-secondary cursor-pointer">
                {busyId === country.id ? "Uploading…" : "Upload PDF or Word"}
                <input
                  className="sr-only"
                  type="file"
                  accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  onChange={(event) => {
                    upload(country.id, event.target.files?.[0]);
                    event.target.value = "";
                  }}
                />
              </label>
            </div>
            <div className="flex flex-col gap-2">
              {files.map((resume) => (
                <article key={resume.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 px-3 py-3">
                  <div className="flex min-w-0 flex-col">
                    <a className="truncate text-sm font-medium text-indigo-600" href={`/api/resumes/file/${resume.id}`} target="_blank" rel="noreferrer">
                      {resume.filename}
                    </a>
                    {resume.is_default && <span className="text-xs text-emerald-700">Default for {country.label}</span>}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {!resume.is_default && (
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={() =>
                          api
                            .makeDefaultResume(resume.id)
                            .then(() => {
                              setNotice(`${resume.filename} is now the default for ${country.label}.`);
                              load();
                            })
                            .catch((err: Error) => setError(err.message))
                        }
                      >
                        Make default
                      </button>
                    )}
                    <button type="button" className="btn-secondary" disabled={busyId === resume.id} onClick={() => fillProfile(resume)}>
                      Fill profile
                    </button>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => api.deleteCountryResume(resume.id).then(load).catch((err: Error) => setError(err.message))}
                    >
                      Remove
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
