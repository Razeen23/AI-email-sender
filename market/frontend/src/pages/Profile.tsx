import { FormEvent, useEffect, useState } from "react";
import { api, profileDraftKey } from "../api";
import Field from "../components/Field";
import PageHeader from "../components/PageHeader";
import type { Education, Experience, Profile, ProfileDraft, Project, Skill } from "../types";

function nid() {
  return crypto.randomUUID();
}

const emptyProfile: Profile = {
  name: "",
  headline: "",
  email: "",
  phone: "",
  city: "",
  country: "",
  linkedin: "",
  github: "",
  portfolio: "",
  languages: [],
  summary: "",
  skills: [],
  experience: [],
  projects: [],
  education: [],
  certifications: [],
  has_base_resume: false,
  base_resume_filename: "",
};

export default function Profile() {
  const [profile, setProfile] = useState<Profile>(emptyProfile);
  const [languages, setLanguages] = useState("");
  const [certifications, setCertifications] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const apply = (next: Profile) => {
    setProfile(next);
    setLanguages(next.languages.join(", "));
    setCertifications(next.certifications.join("\n"));
  };

  const applyDraft = (saved: Profile, draft: ProfileDraft) => {
    const { filled_by: filledBy, ...fields } = draft;
    apply({ ...saved, ...fields, has_base_resume: saved.has_base_resume, base_resume_filename: saved.base_resume_filename });
    setNotice(
      filledBy === "model"
        ? "Fields were filled from the document. Review them, then save."
        : "The model was offline, so only details read directly from the file were filled. Review them, then save.",
    );
  };

  useEffect(() => {
    let active = true;
    api
      .profile()
      .then((saved) => {
        if (!active) return;
        const raw = sessionStorage.getItem(profileDraftKey);
        if (!raw) {
          apply(saved);
          return;
        }
        sessionStorage.removeItem(profileDraftKey);
        applyDraft(saved, JSON.parse(raw) as ProfileDraft);
      })
      .catch((err: Error) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
    };
  }, []);

  const save = (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    const payload: Profile = {
      ...profile,
      languages: languages.split(",").map((item) => item.trim()).filter(Boolean),
      certifications: certifications.split("\n").map((item) => item.trim()).filter(Boolean),
    };
    api
      .saveProfile(payload)
      .then((saved) => {
        apply(saved);
        setNotice("Profile saved.");
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setBusy(false));
  };

  const fillFromFile = (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    api
      .importProfile(file)
      .then((draft) => applyDraft(profile, draft))
      .catch((err: Error) => setError(err.message))
      .finally(() => setBusy(false));
  };

  const setField = (key: "name" | "headline" | "email" | "phone" | "city" | "country" | "linkedin" | "github" | "portfolio" | "summary", value: string) => {
    setProfile((current) => ({ ...current, [key]: value }));
  };
  const setSkill = (id: string, patch: Partial<Skill>) =>
    setProfile((current) => ({ ...current, skills: current.skills.map((item) => (item.id === id ? { ...item, ...patch } : item)) }));
  const setExperience = (id: string, patch: Partial<Experience>) =>
    setProfile((current) => ({ ...current, experience: current.experience.map((item) => (item.id === id ? { ...item, ...patch } : item)) }));
  const setProject = (id: string, patch: Partial<Project>) =>
    setProfile((current) => ({ ...current, projects: current.projects.map((item) => (item.id === id ? { ...item, ...patch } : item)) }));
  const setEducation = (id: string, patch: Partial<Education>) =>
    setProfile((current) => ({ ...current, education: current.education.map((item) => (item.id === id ? { ...item, ...patch } : item)) }));

  return (
    <form onSubmit={save} className="page">
      <PageHeader
        title="Profile"
        description="This is the only source the model may use. It will not invent employers, dates, or skills."
        actions={
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? "Saving…" : "Save profile"}
          </button>
        }
      />
      {notice && <p className="text-sm text-emerald-700">{notice}</p>}
      {error && <p className="text-sm text-rose-600">{error}</p>}

      <section className="card">
        <h2 className="font-semibold">Fill fields from a document</h2>
        <p className="text-sm text-slate-500">
          Upload a resume, PDF, or Word document. The form is filled from that file. Review it, then save. Resumes you send are stored by country on the Resumes page.
        </p>
        <input
          className="text-sm"
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          onChange={(event) => {
            fillFromFile(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
      </section>

      <section className="card">
        <h2 className="font-semibold">Identity</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Field label="Name">
            <input className="field" value={profile.name} onChange={(event) => setField("name", event.target.value)} />
          </Field>
          <Field label="Headline">
            <input className="field" value={profile.headline} onChange={(event) => setField("headline", event.target.value)} placeholder="Nurse, accountant, backend engineer" />
          </Field>
          <Field label="Email">
            <input className="field" type="email" value={profile.email} onChange={(event) => setField("email", event.target.value)} />
          </Field>
          <Field label="Phone">
            <input className="field" value={profile.phone} onChange={(event) => setField("phone", event.target.value)} />
          </Field>
          <Field label="City">
            <input className="field" value={profile.city} onChange={(event) => setField("city", event.target.value)} />
          </Field>
          <Field label="Country you live in">
            <input className="field" value={profile.country} onChange={(event) => setField("country", event.target.value)} />
          </Field>
          <Field label="LinkedIn">
            <input className="field" value={profile.linkedin} onChange={(event) => setField("linkedin", event.target.value)} />
          </Field>
          <Field label="GitHub">
            <input className="field" value={profile.github} onChange={(event) => setField("github", event.target.value)} />
          </Field>
          <Field label="Portfolio">
            <input className="field" value={profile.portfolio} onChange={(event) => setField("portfolio", event.target.value)} />
          </Field>
          <Field label="Languages">
            <input className="field" value={languages} onChange={(event) => setLanguages(event.target.value)} placeholder="English, Spanish" />
          </Field>
        </div>
        <Field label="Summary">
          <textarea className="field" rows={4} value={profile.summary} onChange={(event) => setField("summary", event.target.value)} />
        </Field>
      </section>

      <section className="card">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-semibold">Skills</h2>
          <button type="button" className="btn-secondary" onClick={() => setProfile({ ...profile, skills: [...profile.skills, { id: nid(), group: "", items: "" }] })}>
            Add group
          </button>
        </div>
        {profile.skills.map((skill) => (
          <div key={skill.id} className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_2fr_auto]">
            <input className="field" value={skill.group} placeholder="Group" onChange={(event) => setSkill(skill.id, { group: event.target.value })} />
            <input className="field" value={skill.items} placeholder="Skills" onChange={(event) => setSkill(skill.id, { items: event.target.value })} />
            <button type="button" className="btn-secondary" onClick={() => setProfile({ ...profile, skills: profile.skills.filter((item) => item.id !== skill.id) })}>
              Remove
            </button>
          </div>
        ))}
      </section>

      <section className="card">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-semibold">Experience</h2>
          <button
            type="button"
            className="btn-secondary"
            onClick={() =>
              setProfile({
                ...profile,
                experience: [...profile.experience, { id: nid(), title: "", company: "", dates: "", location: "", bullets: [] }],
              })
            }
          >
            Add role
          </button>
        </div>
        {profile.experience.map((item) => (
          <div key={item.id} className="flex flex-col gap-2 rounded-xl border border-slate-200 p-3">
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              <input className="field" placeholder="Title" value={item.title} onChange={(event) => setExperience(item.id, { title: event.target.value })} />
              <input className="field" placeholder="Company" value={item.company} onChange={(event) => setExperience(item.id, { company: event.target.value })} />
              <input className="field" placeholder="Dates" value={item.dates} onChange={(event) => setExperience(item.id, { dates: event.target.value })} />
              <input className="field" placeholder="Location" value={item.location} onChange={(event) => setExperience(item.id, { location: event.target.value })} />
            </div>
            <textarea
              className="field"
              rows={3}
              placeholder="One bullet per line"
              value={item.bullets.join("\n")}
              onChange={(event) => setExperience(item.id, { bullets: event.target.value.split("\n") })}
            />
            <button type="button" className="btn-secondary w-fit" onClick={() => setProfile({ ...profile, experience: profile.experience.filter((entry) => entry.id !== item.id) })}>
              Remove
            </button>
          </div>
        ))}
      </section>

      <section className="card">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-semibold">Projects</h2>
          <button type="button" className="btn-secondary" onClick={() => setProfile({ ...profile, projects: [...profile.projects, { id: nid(), name: "", tech: "", bullets: [] }] })}>
            Add project
          </button>
        </div>
        {profile.projects.map((item) => (
          <div key={item.id} className="flex flex-col gap-2 rounded-xl border border-slate-200 p-3">
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              <input className="field" placeholder="Name" value={item.name} onChange={(event) => setProject(item.id, { name: event.target.value })} />
              <input className="field" placeholder="Tech" value={item.tech} onChange={(event) => setProject(item.id, { tech: event.target.value })} />
            </div>
            <textarea className="field" rows={3} placeholder="One bullet per line" value={item.bullets.join("\n")} onChange={(event) => setProject(item.id, { bullets: event.target.value.split("\n") })} />
            <button type="button" className="btn-secondary w-fit" onClick={() => setProfile({ ...profile, projects: profile.projects.filter((entry) => entry.id !== item.id) })}>
              Remove
            </button>
          </div>
        ))}
      </section>

      <section className="card">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-semibold">Education</h2>
          <button type="button" className="btn-secondary" onClick={() => setProfile({ ...profile, education: [...profile.education, { id: nid(), degree: "", school: "", dates: "" }] })}>
            Add education
          </button>
        </div>
        {profile.education.map((item) => (
          <div key={item.id} className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_1fr_auto_auto]">
            <input className="field" placeholder="Degree" value={item.degree} onChange={(event) => setEducation(item.id, { degree: event.target.value })} />
            <input className="field" placeholder="School" value={item.school} onChange={(event) => setEducation(item.id, { school: event.target.value })} />
            <input className="field" placeholder="Dates" value={item.dates} onChange={(event) => setEducation(item.id, { dates: event.target.value })} />
            <button type="button" className="btn-secondary" onClick={() => setProfile({ ...profile, education: profile.education.filter((entry) => entry.id !== item.id) })}>
              Remove
            </button>
          </div>
        ))}
        <Field label="Certifications, one per line">
          <textarea className="field" rows={3} value={certifications} onChange={(event) => setCertifications(event.target.value)} />
        </Field>
      </section>
    </form>
  );
}
