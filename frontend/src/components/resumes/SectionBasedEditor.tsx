import React, { useState, useEffect } from 'react';
import { User, GraduationCap, Code2, Briefcase, FolderGit2, Plus, Trash2, Check, Sparkles } from 'lucide-react';
import { CandidateProfile } from '../../types';

interface SectionBasedEditorProps {
  initialProfile: CandidateProfile | null;
  onUpdateLatexContent: (newLatex: string) => void;
  currentTemplateId: string;
}

export const SectionBasedEditor: React.FC<SectionBasedEditorProps> = ({
  initialProfile,
  onUpdateLatexContent,
  currentTemplateId: _currentTemplateId
}) => {
  const [activeTab, setActiveTab] = useState<'profile' | 'education' | 'skills' | 'experience' | 'projects'>('skills');

  // Form states
  const [name, setName] = useState(initialProfile?.name || 'Krishna Patel');
  const [email, setEmail] = useState(initialProfile?.email || 'krishna@example.com');
  const [phone, setPhone] = useState(initialProfile?.phone || '+91 9876543210');
  const [location, setLocation] = useState(initialProfile?.location || 'Pune, India');
  const [githubUrl, setGithubUrl] = useState(initialProfile?.github_url || 'https://github.com/krishna');
  const [linkedinUrl, setLinkedinUrl] = useState(initialProfile?.linkedin_url || 'https://linkedin.com/in/krishna');

  const [college, setCollege] = useState(initialProfile?.college || 'Pune Institute of Computer Technology');
  const [degree, setDegree] = useState(initialProfile?.degree || 'B.Tech Artificial Intelligence & Data Science');
  const [gradYear, setGradYear] = useState(String(initialProfile?.graduation_year || 2028));
  const [cgpa, setCgpa] = useState(String(initialProfile?.cgpa || 8.16));

  const [skillsList, setSkillsList] = useState<Array<{ name: string; category: string }>>(
    (initialProfile?.skills || []).map((s: any) => ({
      name: typeof s === 'string' ? s : s.name,
      category: (typeof s === 'object' && s.category) ? s.category : 'General'
    }))
  );

  const [experiences, setExperiences] = useState<Array<{ title: string; company: string; duration: string; description: string }>>(
    (initialProfile?.experience || []).map((e: any) => ({
      title: e.title || '',
      company: e.company || '',
      duration: e.duration || '',
      description: e.description || ''
    }))
  );

  const [projects, setProjects] = useState<Array<{ title: string; tech_stack: string[]; description: string; url: string }>>(
    (initialProfile?.projects || []).map((p: any) => ({
      title: p.title || '',
      tech_stack: p.tech_stack || [],
      description: p.description || '',
      url: p.url || ''
    }))
  );

  const [isSaved, setIsSaved] = useState(false);

  // Sync with initialProfile when it loads
  useEffect(() => {
    if (initialProfile) {
      if (initialProfile.name) setName(initialProfile.name);
      if (initialProfile.email) setEmail(initialProfile.email);
      if (initialProfile.phone) setPhone(initialProfile.phone);
      if (initialProfile.location) setLocation(initialProfile.location);
      if (initialProfile.github_url) setGithubUrl(initialProfile.github_url);
      if (initialProfile.linkedin_url) setLinkedinUrl(initialProfile.linkedin_url);
      if (initialProfile.college) setCollege(initialProfile.college);
      if (initialProfile.degree) setDegree(initialProfile.degree);
      if (initialProfile.graduation_year) setGradYear(String(initialProfile.graduation_year));
      if (initialProfile.cgpa) setCgpa(String(initialProfile.cgpa));
      if (initialProfile.skills) {
        setSkillsList(initialProfile.skills.map((s: any) => ({
          name: typeof s === 'string' ? s : s.name,
          category: (typeof s === 'object' && s.category) ? s.category : 'General'
        })));
      }
      if (initialProfile.experience) {
        setExperiences(initialProfile.experience.map((e: any) => ({
          title: e.title || '',
          company: e.company || '',
          duration: e.duration || '',
          description: e.description || ''
        })));
      }
      if (initialProfile.projects) {
        setProjects(initialProfile.projects.map((p: any) => ({
          title: p.title || '',
          tech_stack: p.tech_stack || [],
          description: p.description || '',
          url: p.url || ''
        })));
      }
    }
  }, [initialProfile]);

  const handleApplyChanges = () => {
    // Generate updated LaTeX locally using safe template construction
    const esc = (txt: string) => (txt || '').replace(/[&%$#_{}~^\\]/g, '\\$&');

    const langs = skillsList.filter(s => /lang/i.test(s.category)).map(s => esc(s.name)).join(', ') || 'Python, C++, SQL, JavaScript';
    const fws = skillsList.filter(s => /framework|lib|front|back|web/i.test(s.category)).map(s => esc(s.name)).join(', ') || 'FastAPI, React, PyTorch, Node.js';
    const tools = skillsList.filter(s => /tool|platform|cloud|devops|db/i.test(s.category)).map(s => esc(s.name)).join(', ') || 'Docker, Git, PostgreSQL, Linux';

    const expTex = experiences.map(e => `\\textbf{${esc(e.title)}} \\hfill ${esc(e.duration)} \\\\
\\textit{${esc(e.company)}} \\\\
\\vspace{-4pt}
\\begin{itemize}[leftmargin=12pt, topsep=2pt, itemsep=1pt]
  \\item ${esc(e.description)}
\\end{itemize}
\\vspace{3pt}
`).join('');

    const projTex = projects.map(p => `\\textbf{${esc(p.title)}} | \\textit{${esc((p.tech_stack || []).join(', '))}} ${p.url ? `\\hfill \\href{${esc(p.url)}}{[Code]}` : ''} \\\\
\\vspace{-4pt}
\\begin{itemize}[leftmargin=12pt, topsep=2pt, itemsep=1pt]
  \\item ${esc(p.description)}
\\end{itemize}
\\vspace{3pt}
`).join('');

    const updatedLatex = `\\documentclass[10pt,a4paper]{article}
\\usepackage[utf8]{inputenc}
\\usepackage[margin=0.6in]{geometry}
\\usepackage{hyperref}
\\usepackage{enumitem}
\\usepackage{titlesec}
\\usepackage{parskip}

\\hypersetup{colorlinks=true, linkcolor=black, filecolor=black, urlcolor=blue}
\\titleformat{\\section}{\\large\\bfseries}{}{0em}{}[\\titlerule]
\\titlespacing*{\\section}{0pt}{5pt}{3pt}
\\pagestyle{empty}

\\begin{document}

\\begin{center}
  {\\Huge \\textbf{${esc(name)}}} \\\\[4pt]
  ${esc(location)} $\\cdot$ ${esc(phone)} $\\cdot$ \\href{mailto:${esc(email)}}{${esc(email)}} \\\\[2pt]
  \\href{${esc(githubUrl)}}{GitHub} $\\cdot$ \\href{${esc(linkedinUrl)}}{LinkedIn}
\\end{center}
\\vspace{-4pt}

\\section*{Education}
\\textbf{${esc(college)}} \\hfill Expected ${esc(gradYear)} \\\\
${esc(degree)} \\hfill CGPA: ${esc(cgpa)} / 10.0 \\\\
\\vspace{2pt}

\\section*{Technical Skills}
\\begin{itemize}[leftmargin=12pt, topsep=2pt, itemsep=2pt]
  \\item \\textbf{Languages:} ${langs}
  \\item \\textbf{Frameworks \\& Libraries:} ${fws}
  \\item \\textbf{Tools \\& Platforms:} ${tools}
\\end{itemize}
\\vspace{2pt}

${experiences.length > 0 ? `\\section*{Experience}\n${expTex}` : ''}

\\section*{Key Technical Projects}
${projTex || '% No projects added\n'}

\\end{document}
`;

    onUpdateLatexContent(updatedLatex);
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 2500);
  };

  const addSkill = () => {
    setSkillsList([...skillsList, { name: 'New Skill', category: 'Frameworks' }]);
  };

  const removeSkill = (index: number) => {
    setSkillsList(skillsList.filter((_, i) => i !== index));
  };

  const addProject = () => {
    setProjects([
      ...projects,
      { title: 'New Software Project', tech_stack: ['Python', 'FastAPI'], description: 'Designed and deployed scalable services.', url: '' }
    ]);
  };

  const removeProject = (index: number) => {
    setProjects(projects.filter((_, i) => i !== index));
  };

  return (
    <div className="flex flex-col h-full rounded-xl border border-white/[0.08] bg-[var(--color-paper-2)] overflow-hidden">
      {/* Editor Sub-Header Nav */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 bg-[var(--color-paper)] border-b border-white/[0.08]">
        <div className="flex items-center gap-1 overflow-x-auto py-0.5">
          <button
            type="button"
            onClick={() => setActiveTab('profile')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors ${
              activeTab === 'profile'
                ? 'bg-white/[0.10] text-white shadow-sm ring-1 ring-white/10'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
            }`}
          >
            <User className="w-3.5 h-3.5 text-slate-400" />
            <span>Contact</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('education')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors ${
              activeTab === 'education'
                ? 'bg-white/[0.10] text-white shadow-sm ring-1 ring-white/10'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
            }`}
          >
            <GraduationCap className="w-3.5 h-3.5 text-slate-400" />
            <span>Education</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('skills')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors ${
              activeTab === 'skills'
                ? 'bg-white/[0.10] text-white shadow-sm ring-1 ring-white/10'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
            }`}
          >
            <Code2 className="w-3.5 h-3.5 text-slate-400" />
            <span>Skills ({skillsList.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('experience')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors ${
              activeTab === 'experience'
                ? 'bg-white/[0.10] text-white shadow-sm ring-1 ring-white/10'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
            }`}
          >
            <Briefcase className="w-3.5 h-3.5 text-slate-400" />
            <span>Experience ({experiences.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('projects')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors ${
              activeTab === 'projects'
                ? 'bg-white/[0.10] text-white shadow-sm ring-1 ring-white/10'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
            }`}
          >
            <FolderGit2 className="w-3.5 h-3.5 text-slate-400" />
            <span>Projects ({projects.length})</span>
          </button>
        </div>

        <button
          type="button"
          onClick={handleApplyChanges}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-semibold transition-colors ${
            isSaved
              ? 'bg-emerald-400/20 text-emerald-300 border border-emerald-400/40'
              : 'bg-emerald-400 hover:bg-emerald-300 text-[var(--color-accent-ink)] shadow-sm'
          }`}
        >
          {isSaved ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Sparkles className="w-3.5 h-3.5" />}
          <span>{isSaved ? 'Synchronized!' : 'Sync to LaTeX'}</span>
        </button>
      </div>

      {/* Editor Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Contact Tab */}
        {activeTab === 'profile' && (
          <div className="space-y-4">
            <div>
              <h4 className="text-[13px] font-semibold text-white">Candidate Header & Contact</h4>
              <p className="text-[11px] text-slate-400">Core identity details displayed at the top of your ATS resume.</p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] font-medium text-slate-400">Full Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  className="w-full mt-1 bg-[var(--color-paper)] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-400/60 focus:ring-1 focus:ring-emerald-400/30"
                />
              </div>
              <div>
                <label className="text-[11px] font-medium text-slate-400">Email Address</label>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  className="w-full mt-1 bg-[var(--color-paper)] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-400/60 focus:ring-1 focus:ring-emerald-400/30"
                />
              </div>
              <div>
                <label className="text-[11px] font-medium text-slate-400">Phone</label>
                <input
                  type="text"
                  value={phone}
                  onChange={e => setPhone(e.target.value)}
                  className="w-full mt-1 bg-[var(--color-paper)] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-400/60 focus:ring-1 focus:ring-emerald-400/30"
                />
              </div>
              <div>
                <label className="text-[11px] font-medium text-slate-400">Location</label>
                <input
                  type="text"
                  value={location}
                  onChange={e => setLocation(e.target.value)}
                  className="w-full mt-1 bg-[var(--color-paper)] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-400/60 focus:ring-1 focus:ring-emerald-400/30"
                />
              </div>
              <div>
                <label className="text-[11px] font-medium text-slate-400">GitHub Profile URL</label>
                <input
                  type="url"
                  value={githubUrl}
                  onChange={e => setGithubUrl(e.target.value)}
                  className="w-full mt-1 bg-[var(--color-paper)] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-400/60 focus:ring-1 focus:ring-emerald-400/30"
                />
              </div>
              <div>
                <label className="text-[11px] font-medium text-slate-400">LinkedIn Profile URL</label>
                <input
                  type="url"
                  value={linkedinUrl}
                  onChange={e => setLinkedinUrl(e.target.value)}
                  className="w-full mt-1 bg-[var(--color-paper)] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-400/60 focus:ring-1 focus:ring-emerald-400/30"
                />
              </div>
            </div>
          </div>
        )}

        {/* Education Tab */}
        {activeTab === 'education' && (
          <div className="space-y-4">
            <div>
              <h4 className="text-[13px] font-semibold text-white">Academic Credentials</h4>
              <p className="text-[11px] text-slate-400">Educational degrees, institution name, expected graduation year, and GPA.</p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="sm:col-span-2">
                <label className="text-[11px] font-medium text-slate-400">College / University</label>
                <input
                  type="text"
                  value={college}
                  onChange={e => setCollege(e.target.value)}
                  className="w-full mt-1 bg-[var(--color-paper)] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-400/60 focus:ring-1 focus:ring-emerald-400/30"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="text-[11px] font-medium text-slate-400">Degree & Specialization</label>
                <input
                  type="text"
                  value={degree}
                  onChange={e => setDegree(e.target.value)}
                  className="w-full mt-1 bg-[var(--color-paper)] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-400/60 focus:ring-1 focus:ring-emerald-400/30"
                />
              </div>
              <div>
                <label className="text-[11px] font-medium text-slate-400">Graduation Year</label>
                <input
                  type="text"
                  value={gradYear}
                  onChange={e => setGradYear(e.target.value)}
                  className="w-full mt-1 bg-[var(--color-paper)] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-400/60 focus:ring-1 focus:ring-emerald-400/30"
                />
              </div>
              <div>
                <label className="text-[11px] font-medium text-slate-400">CGPA / Grade</label>
                <input
                  type="text"
                  value={cgpa}
                  onChange={e => setCgpa(e.target.value)}
                  className="w-full mt-1 bg-[var(--color-paper)] border border-white/[0.08] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-400/60 focus:ring-1 focus:ring-emerald-400/30"
                />
              </div>
            </div>
          </div>
        )}

        {/* Skills Tab */}
        {activeTab === 'skills' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-[13px] font-semibold text-white">
                  Technical Skills Inventory ({skillsList.length})
                </h4>
                <p className="text-[11px] text-slate-400">Categorized technical skills mapped directly to ATS parser filters.</p>
              </div>
              <button
                type="button"
                onClick={addSkill}
                className="inline-flex items-center gap-1 text-[11px] text-emerald-400 hover:text-emerald-300 font-medium px-2 py-1 rounded bg-emerald-400/[0.08] border border-emerald-400/20"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Skill</span>
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {skillsList.map((skill, idx) => (
                <div key={idx} className="flex items-center gap-2 p-2 rounded-lg bg-[var(--color-paper-3)] border border-white/[0.06]">
                  <input
                    type="text"
                    value={skill.name}
                    onChange={e => {
                      const updated = [...skillsList];
                      updated[idx].name = e.target.value;
                      setSkillsList(updated);
                    }}
                    className="flex-1 bg-[var(--color-paper)] border border-white/[0.08] rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:border-emerald-400/60"
                    placeholder="Skill name"
                  />
                  <select
                    value={skill.category}
                    onChange={e => {
                      const updated = [...skillsList];
                      updated[idx].category = e.target.value;
                      setSkillsList(updated);
                    }}
                    className="bg-[var(--color-paper)] border border-white/[0.08] rounded px-2 py-1 text-[11px] text-slate-300 focus:outline-none focus:border-emerald-400/60"
                  >
                    <option value="Languages">Languages</option>
                    <option value="Frameworks">Frameworks</option>
                    <option value="Tools">Tools</option>
                    <option value="Core Competencies">Core</option>
                  </select>
                  <button
                    type="button"
                    onClick={() => removeSkill(idx)}
                    className="p-1 text-slate-500 hover:text-rose-400 transition-colors"
                    title="Remove skill"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Experience Tab */}
        {activeTab === 'experience' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-[13px] font-semibold text-white">Work Experience & Internships</h4>
                <p className="text-[11px] text-slate-400">Professional track record highlighting impact with action verbs.</p>
              </div>
              <button
                type="button"
                onClick={() => setExperiences([...experiences, { title: 'Software Intern', company: 'Company', duration: 'Summer 2025', description: 'Built production services.' }])}
                className="inline-flex items-center gap-1 text-[11px] text-emerald-400 hover:text-emerald-300 font-medium px-2 py-1 rounded bg-emerald-400/[0.08] border border-emerald-400/20"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Experience</span>
              </button>
            </div>

            <div className="space-y-3">
              {experiences.map((exp, idx) => (
                <div key={idx} className="p-3.5 rounded-lg bg-[var(--color-paper-3)] border border-white/[0.06] space-y-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <input
                      type="text"
                      value={exp.title}
                      onChange={e => {
                        const upd = [...experiences];
                        upd[idx].title = e.target.value;
                        setExperiences(upd);
                      }}
                      className="font-semibold text-xs bg-[var(--color-paper)] border border-white/[0.08] rounded px-2.5 py-1 text-white w-1/2 focus:outline-none focus:border-emerald-400/60"
                      placeholder="Role Title"
                    />
                    <button
                      type="button"
                      onClick={() => setExperiences(experiences.filter((_, i) => i !== idx))}
                      className="p-1 text-slate-500 hover:text-rose-400 transition-colors"
                      title="Remove experience"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="text"
                      value={exp.company}
                      onChange={e => {
                        const upd = [...experiences];
                        upd[idx].company = e.target.value;
                        setExperiences(upd);
                      }}
                      className="text-xs bg-[var(--color-paper)] border border-white/[0.08] rounded px-2 py-1 text-slate-300 focus:outline-none focus:border-emerald-400/60"
                      placeholder="Company Name"
                    />
                    <input
                      type="text"
                      value={exp.duration}
                      onChange={e => {
                        const upd = [...experiences];
                        upd[idx].duration = e.target.value;
                        setExperiences(upd);
                      }}
                      className="text-xs bg-[var(--color-paper)] border border-white/[0.08] rounded px-2 py-1 text-slate-300 focus:outline-none focus:border-emerald-400/60"
                      placeholder="Duration (e.g. Jun - Aug 2025)"
                    />
                  </div>
                  <textarea
                    value={exp.description}
                    onChange={e => {
                      const upd = [...experiences];
                      upd[idx].description = e.target.value;
                      setExperiences(upd);
                    }}
                    rows={2}
                    className="w-full text-xs bg-[var(--color-paper)] border border-white/[0.08] rounded px-2 py-1.5 text-slate-300 focus:outline-none focus:border-emerald-400/60 leading-relaxed"
                    placeholder="Key deliverable bullet point"
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Projects Tab */}
        {activeTab === 'projects' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-[13px] font-semibold text-white">Technical Projects ({projects.length})</h4>
                <p className="text-[11px] text-slate-400">Open-source, academic, or production applications with verifiable links.</p>
              </div>
              <button
                type="button"
                onClick={addProject}
                className="inline-flex items-center gap-1 text-[11px] text-emerald-400 hover:text-emerald-300 font-medium px-2 py-1 rounded bg-emerald-400/[0.08] border border-emerald-400/20"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Project</span>
              </button>
            </div>

            <div className="space-y-3">
              {projects.map((proj, idx) => (
                <div key={idx} className="p-3.5 rounded-lg bg-[var(--color-paper-3)] border border-white/[0.06] space-y-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <input
                      type="text"
                      value={proj.title}
                      onChange={e => {
                        const upd = [...projects];
                        upd[idx].title = e.target.value;
                        setProjects(upd);
                      }}
                      className="font-semibold text-xs bg-[var(--color-paper)] border border-white/[0.08] rounded px-2.5 py-1 text-white w-2/3 focus:outline-none focus:border-emerald-400/60"
                      placeholder="Project Title"
                    />
                    <button
                      type="button"
                      onClick={() => removeProject(idx)}
                      className="p-1 text-slate-500 hover:text-rose-400 transition-colors"
                      title="Remove project"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="text"
                      value={(proj.tech_stack || []).join(', ')}
                      onChange={e => {
                        const upd = [...projects];
                        upd[idx].tech_stack = e.target.value.split(',').map(s => s.trim()).filter(Boolean);
                        setProjects(upd);
                      }}
                      className="text-xs bg-[var(--color-paper)] border border-white/[0.08] rounded px-2 py-1 text-slate-300 focus:outline-none focus:border-emerald-400/60"
                      placeholder="Tech Stack (comma separated)"
                    />
                    <input
                      type="text"
                      value={proj.url || ''}
                      onChange={e => {
                        const upd = [...projects];
                        upd[idx].url = e.target.value;
                        setProjects(upd);
                      }}
                      className="text-xs bg-[var(--color-paper)] border border-white/[0.08] rounded px-2 py-1 text-slate-300 focus:outline-none focus:border-emerald-400/60"
                      placeholder="GitHub / Live URL"
                    />
                  </div>
                  <textarea
                    value={proj.description}
                    onChange={e => {
                      const upd = [...projects];
                      upd[idx].description = e.target.value;
                      setProjects(upd);
                    }}
                    rows={2}
                    className="w-full text-xs bg-[var(--color-paper)] border border-white/[0.08] rounded px-2 py-1.5 text-slate-300 focus:outline-none focus:border-emerald-400/60 leading-relaxed"
                    placeholder="Project architecture and outcomes description"
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
