import { FormEvent, ReactNode, useEffect, useState } from "react";
import PageHeader from "../components/PageHeader";
import { api } from "../api";
import type { EducationEntry, ExperienceEntry, ProfileDocument, ProjectEntry, SkillGroup } from "../types";

function nid(): string {
  return crypto.randomUUID().replace(/-/g, "").slice(0, 12);
}

function moveItem<T>(items: T[], index: number, direction: -1 | 1): T[] {
  const next = index + direction;
  if (next < 0 || next >= items.length) return items;
  const copy = items.slice();
  const [item] = copy.splice(index, 1);
  copy.splice(next, 0, item);
  return copy;
}

function RowActions({
  index,
  total,
  onMove,
  onRemove,
}: {
  index: number;
  total: number;
  onMove: (direction: -1 | 1) => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      <button type="button" className="btn-secondary" disabled={index === 0} onClick={() => onMove(-1)}>
        Move up
      </button>
      <button type="button" className="btn-secondary" disabled={index === total - 1} onClick={() => onMove(1)}>
        Move down
      </button>
      <button type="button" className="btn-danger" onClick={onRemove}>
        Remove
      </button>
    </div>
  );
}

function LinesField({
  label,
  value,
  onChange,
  rows = 4,
}: {
  label: string;
  value: string[];
  onChange: (next: string[]) => void;
  rows?: number;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-slate-500">{label}</span>
      <textarea className="field" rows={rows} value={value.join("\n")} onChange={(event) => onChange(event.target.value.split("\n"))} />
    </label>
  );
}

function Field({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-slate-500">{label}</span>
      <input className="field" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

const emptyExperience = (): ExperienceEntry => ({
  id: nid(),
  title: "",
  company: "",
  dates: "",
  location: "",
  bullets: [""],
});

const emptyProject = (): ProjectEntry => ({ id: nid(), name: "", tech: "", bullets: [""] });
const emptyEducation = (): EducationEntry => ({ id: nid(), degree: "", dates: "", school: "" });
const emptySkill = (): SkillGroup => ({ id: nid(), group: "", items: "" });

export default function Profile() {
  const [profile, setProfile] = useState<ProfileDocument | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmBase, setConfirmBase] = useState(false);
  const [confirmUpload, setConfirmUpload] = useState(false);
  const [uploadRegion, setUploadRegion] = useState("BOTH");
  const [file, setFile] = useState<File | null>(null);

  useEffect(() => {
    api
      .profile()
      .then(setProfile)
      .catch((err: Error) => setError(err.message));
  }, []);

  const save = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!profile) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const saved = await api.saveProfile(profile);
      setProfile(saved);
      setNotice("Profile saved. New resumes and emails will use this.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  };

  const importBase = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const imported = await api.importBaseProfile();
      setProfile(imported);
      setConfirmBase(false);
      setNotice("Re-imported both base CVs.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBusy(false);
    }
  };

  const importFile = async () => {
    if (!file) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const imported = await api.importDocx(file, uploadRegion);
      setProfile(imported);
      setConfirmUpload(false);
      setFile(null);
      setNotice("Imported the Word file into your profile.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBusy(false);
    }
  };

  if (!profile && !error) return <p className="text-sm text-slate-500">Loading profile…</p>;
  if (!profile) return <p className="text-sm text-rose-600">{error}</p>;

  const update = (next: ProfileDocument) => setProfile(next);

  return (
    <form className="page" onSubmit={save}>
      <PageHeader
        title="Profile"
        description="This is the source for tailored resumes and application emails. Add a job or project here, then generate again."
        actions={
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? "Saving…" : "Save profile"}
          </button>
        }
      />

      {error && <p className="rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
      {notice && <p className="rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{notice}</p>}

      <Section title="Import">
        <p className="text-sm text-slate-500">
          Import replaces the saved jobs, projects, skills, and summaries. Save any edits you want to keep before you do this.
        </p>
        <div className="card">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={confirmBase} onChange={(event) => setConfirmBase(event.target.checked)} />
            Replace the profile with the India and UAE base CVs
          </label>
          <button type="button" className="btn-secondary self-start" disabled={busy || !confirmBase} onClick={importBase}>
            Re-import base CVs
          </button>
        </div>
        <div className="card">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-slate-500">Word file</span>
              <input
                className="field"
                type="file"
                accept=".docx"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-slate-500">Which summary to update</span>
              <select className="field" value={uploadRegion} onChange={(event) => setUploadRegion(event.target.value)}>
                <option value="BOTH">Both regions</option>
                <option value="INR">India summary</option>
                <option value="UAE">UAE summary</option>
              </select>
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={confirmUpload} onChange={(event) => setConfirmUpload(event.target.checked)} />
            Replace shared profile details with this file
          </label>
          <button type="button" className="btn-secondary self-start" disabled={busy || !confirmUpload || !file} onClick={importFile}>
            Import Word file
          </button>
        </div>
      </Section>

      <Section title="Contact">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <Field label="Name" value={profile.identity.name} onChange={(name) => update({ ...profile, identity: { ...profile.identity, name } })} />
          <Field
            label="Headline"
            value={profile.identity.headline}
            onChange={(headline) => update({ ...profile, identity: { ...profile.identity, headline } })}
          />
          <Field label="Email" value={profile.identity.email} onChange={(email) => update({ ...profile, identity: { ...profile.identity, email } })} />
          <Field
            label="Languages"
            value={profile.identity.languages.join(", ")}
            onChange={(value) =>
              update({
                ...profile,
                identity: { ...profile.identity, languages: value.split(",").map((part) => part.trim()) },
              })
            }
          />
          <Field
            label="India phone"
            value={profile.identity.phones.india}
            onChange={(india) => update({ ...profile, identity: { ...profile.identity, phones: { ...profile.identity.phones, india } } })}
          />
          <Field
            label="UAE phone"
            value={profile.identity.phones.uae}
            onChange={(uae) => update({ ...profile, identity: { ...profile.identity, phones: { ...profile.identity.phones, uae } } })}
          />
          <Field
            label="India location"
            value={profile.identity.location.inr}
            onChange={(inr) => update({ ...profile, identity: { ...profile.identity, location: { ...profile.identity.location, inr } } })}
          />
          <Field
            label="UAE location"
            value={profile.identity.location.uae}
            onChange={(uae) => update({ ...profile, identity: { ...profile.identity, location: { ...profile.identity.location, uae } } })}
          />
          <Field
            label="LinkedIn"
            value={profile.identity.links.linkedin}
            onChange={(linkedin) => update({ ...profile, identity: { ...profile.identity, links: { ...profile.identity.links, linkedin } } })}
          />
          <Field
            label="GitHub"
            value={profile.identity.links.github}
            onChange={(github) => update({ ...profile, identity: { ...profile.identity, links: { ...profile.identity.links, github } } })}
          />
          <Field
            label="Portfolio"
            value={profile.identity.links.portfolio}
            onChange={(portfolio) => update({ ...profile, identity: { ...profile.identity, links: { ...profile.identity.links, portfolio } } })}
          />
        </div>
      </Section>

      <Section title="Summaries">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-slate-500">India</span>
          <textarea
            className="field"
            rows={4}
            value={profile.summaries.inr}
            onChange={(event) => update({ ...profile, summaries: { ...profile.summaries, inr: event.target.value } })}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-slate-500">UAE</span>
          <textarea
            className="field"
            rows={4}
            value={profile.summaries.uae}
            onChange={(event) => update({ ...profile, summaries: { ...profile.summaries, uae: event.target.value } })}
          />
        </label>
      </Section>

      <Section
        title="Skills"
        action={
          <button type="button" className="btn-secondary" onClick={() => update({ ...profile, skills: [...profile.skills, emptySkill()] })}>
            Add group
          </button>
        }
      >
        {profile.skills.map((skill, index) => (
          <article key={skill.id} className="card">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Field
                label="Group"
                value={skill.group}
                onChange={(group) => {
                  const skills = profile.skills.slice();
                  skills[index] = { ...skill, group };
                  update({ ...profile, skills });
                }}
              />
              <Field
                label="Tools, comma separated"
                value={skill.items}
                onChange={(items) => {
                  const skills = profile.skills.slice();
                  skills[index] = { ...skill, items };
                  update({ ...profile, skills });
                }}
              />
            </div>
            <RowActions
              index={index}
              total={profile.skills.length}
              onMove={(direction) => update({ ...profile, skills: moveItem(profile.skills, index, direction) })}
              onRemove={() => update({ ...profile, skills: profile.skills.filter((item) => item.id !== skill.id) })}
            />
          </article>
        ))}
      </Section>

      <Section
        title="Experience"
        action={
          <button type="button" className="btn-secondary" onClick={() => update({ ...profile, experience: [...profile.experience, emptyExperience()] })}>
            Add experience
          </button>
        }
      >
        {profile.experience.map((entry, index) => (
          <article key={entry.id} className="card">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Field
                label="Title"
                value={entry.title}
                onChange={(title) => {
                  const experience = profile.experience.slice();
                  experience[index] = { ...entry, title };
                  update({ ...profile, experience });
                }}
              />
              <Field
                label="Company"
                value={entry.company}
                onChange={(company) => {
                  const experience = profile.experience.slice();
                  experience[index] = { ...entry, company };
                  update({ ...profile, experience });
                }}
              />
              <Field
                label="Dates"
                value={entry.dates}
                onChange={(dates) => {
                  const experience = profile.experience.slice();
                  experience[index] = { ...entry, dates };
                  update({ ...profile, experience });
                }}
              />
              <Field
                label="Location"
                value={entry.location}
                onChange={(location) => {
                  const experience = profile.experience.slice();
                  experience[index] = { ...entry, location };
                  update({ ...profile, experience });
                }}
              />
            </div>
            <LinesField
              label="Bullets, one per line"
              value={entry.bullets}
              onChange={(bullets) => {
                const experience = profile.experience.slice();
                experience[index] = { ...entry, bullets };
                update({ ...profile, experience });
              }}
            />
            <RowActions
              index={index}
              total={profile.experience.length}
              onMove={(direction) => update({ ...profile, experience: moveItem(profile.experience, index, direction) })}
              onRemove={() => update({ ...profile, experience: profile.experience.filter((item) => item.id !== entry.id) })}
            />
          </article>
        ))}
      </Section>

      <Section
        title="Projects"
        action={
          <button type="button" className="btn-secondary" onClick={() => update({ ...profile, projects: [...profile.projects, emptyProject()] })}>
            Add project
          </button>
        }
      >
        {profile.projects.map((project, index) => (
          <article key={project.id} className="card">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Field
                label="Name"
                value={project.name}
                onChange={(name) => {
                  const projects = profile.projects.slice();
                  projects[index] = { ...project, name };
                  update({ ...profile, projects });
                }}
              />
              <Field
                label="Tech"
                value={project.tech}
                onChange={(tech) => {
                  const projects = profile.projects.slice();
                  projects[index] = { ...project, tech };
                  update({ ...profile, projects });
                }}
              />
            </div>
            <LinesField
              label="Bullets, one per line"
              value={project.bullets}
              onChange={(bullets) => {
                const projects = profile.projects.slice();
                projects[index] = { ...project, bullets };
                update({ ...profile, projects });
              }}
            />
            <RowActions
              index={index}
              total={profile.projects.length}
              onMove={(direction) => update({ ...profile, projects: moveItem(profile.projects, index, direction) })}
              onRemove={() => update({ ...profile, projects: profile.projects.filter((item) => item.id !== project.id) })}
            />
          </article>
        ))}
      </Section>

      <Section
        title="Education"
        action={
          <button type="button" className="btn-secondary" onClick={() => update({ ...profile, education: [...profile.education, emptyEducation()] })}>
            Add education
          </button>
        }
      >
        {profile.education.map((entry, index) => (
          <article key={entry.id} className="card">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Field
                label="Degree"
                value={entry.degree}
                onChange={(degree) => {
                  const education = profile.education.slice();
                  education[index] = { ...entry, degree };
                  update({ ...profile, education });
                }}
              />
              <Field
                label="Dates"
                value={entry.dates}
                onChange={(dates) => {
                  const education = profile.education.slice();
                  education[index] = { ...entry, dates };
                  update({ ...profile, education });
                }}
              />
              <Field
                label="School"
                value={entry.school}
                onChange={(school) => {
                  const education = profile.education.slice();
                  education[index] = { ...entry, school };
                  update({ ...profile, education });
                }}
              />
            </div>
            <RowActions
              index={index}
              total={profile.education.length}
              onMove={(direction) => update({ ...profile, education: moveItem(profile.education, index, direction) })}
              onRemove={() => update({ ...profile, education: profile.education.filter((item) => item.id !== entry.id) })}
            />
          </article>
        ))}
      </Section>

      <Section title="Certifications and awards">
        <LinesField label="Certifications, one per line" value={profile.certifications} onChange={(certifications) => update({ ...profile, certifications })} />
        <LinesField label="Awards, one per line" value={profile.awards} onChange={(awards) => update({ ...profile, awards })} />
      </Section>
    </form>
  );
}
