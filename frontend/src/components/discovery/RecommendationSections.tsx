import React, { useState } from 'react';
import { 
  Sparkles, 
  Clock, 
  Globe, 
  Cpu, 
  Code, 
  Hourglass, 
  FolderGit2, 
  MapPin, 
  DollarSign, 
  Send, 
  FileText, 
  Bookmark, 
  X, 
  ExternalLink,
  ChevronRight,
  ShieldCheck,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import { OpportunityItem, CuratedRecommendationsResponse } from '../../types';

interface RecommendationSectionsProps {
  recommendations: CuratedRecommendationsResponse | null;
  loading: boolean;
  onViewDetail: (id: number) => void;
  onToggleSave: (id: number) => void;
  onDismissClick: (item: OpportunityItem) => void;
  onTailorResume: (id: number) => void;
  onPrepareApply: (id: number) => void;
}

export const RecommendationSections: React.FC<RecommendationSectionsProps> = ({
  recommendations,
  loading,
  onViewDetail,
  onToggleSave,
  onDismissClick,
  onTailorResume,
  onPrepareApply
}) => {
  const [activeCategory, setActiveCategory] = useState<string>('all');

  if (loading) {
    return (
      <div className="p-8 text-center rounded-xl bg-dark-850 border border-dark-750">
        <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-xs text-slate-400 font-medium">Curating personalized recommendation sections from live database records...</p>
      </div>
    );
  }

  if (!recommendations) return null;

  const sections = [
    {
      id: 'best_matches',
      title: 'Best Matches',
      subtitle: 'Highest profile compatibility based on your technical skills, experience, and eligibility',
      icon: Sparkles,
      iconColor: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
      items: recommendations.best_matches || []
    },
    {
      id: 'based_on_projects',
      title: 'Opportunities Based on My Projects',
      subtitle: 'Roles specifically matching technology stacks and domains from your verified GitHub portfolio',
      icon: FolderGit2,
      iconColor: 'text-emerald-300 bg-purple-500/10 border-purple-500/30',
      items: recommendations.based_on_projects || []
    },
    {
      id: 'recently_posted',
      title: 'Recently Posted',
      subtitle: 'Fresh internship listings discovered within the last 14 days with strong candidate alignment',
      icon: Clock,
      iconColor: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
      items: recommendations.recently_posted || []
    },
    {
      id: 'closing_soon',
      title: 'Closing Soon',
      subtitle: 'Application portals with approaching deadlines in the next 7 days — prioritize applying now',
      icon: Hourglass,
      iconColor: 'text-rose-400 bg-rose-500/10 border-rose-500/30',
      items: recommendations.closing_soon || []
    },
    {
      id: 'remote_opportunities',
      title: 'Remote Opportunities',
      subtitle: 'Flexible asynchronous internships compatible with current college schedules',
      icon: Globe,
      iconColor: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
      items: recommendations.remote_opportunities || []
    },
    {
      id: 'aiml_internships',
      title: 'AI/ML Internships',
      subtitle: 'Roles in Artificial Intelligence, Deep Learning, NLP, Computer Vision, and Generative AI',
      icon: Cpu,
      iconColor: 'text-teal-400 bg-teal-500/10 border-teal-500/30',
      items: recommendations.aiml_internships || []
    },
    {
      id: 'fullstack_internships',
      title: 'Full Stack & Software Engineering',
      subtitle: 'Modern frontend, backend, microservices, and web application internships',
      icon: Code,
      iconColor: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/30',
      items: recommendations.fullstack_internships || []
    }
  ];

  const filteredSections = activeCategory === 'all' 
    ? sections 
    : sections.filter(s => s.id === activeCategory);

  return (
    <div className="space-y-6 mb-8">
      {/* Category Pills Header */}
      <div className="flex items-center justify-between pb-1 overflow-x-auto no-scrollbar gap-2">
        <div className="flex items-center space-x-1.5 flex-nowrap">
          <button
            onClick={() => setActiveCategory('all')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition ${
              activeCategory === 'all'
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                : 'bg-dark-800 text-slate-400 hover:text-[var(--color-ink)] border border-dark-700/60'
            }`}
          >
            All Sections (7)
          </button>
          {sections.map(s => {
            const Icon = s.icon;
            const active = activeCategory === s.id;
            return (
              <button
                key={s.id}
                onClick={() => setActiveCategory(s.id)}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition ${
                  active
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                    : 'bg-dark-800 text-slate-400 hover:text-[var(--color-ink)] border border-dark-700/60'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{s.title}</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-dark-900 text-slate-300">
                  {s.items.length}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Render Each Recommendation Section */}
      {filteredSections.map(section => {
        const Icon = section.icon;
        if (!section.items || section.items.length === 0) return null;

        return (
          <div key={section.id} className="rounded-xl bg-dark-850 border border-dark-700/80 p-5 space-y-4">
            {/* Section Title */}
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-3">
                <div className={`w-9 h-9 rounded-xl border flex items-center justify-center flex-shrink-0 ${section.iconColor}`}>
                  <Icon className="w-4 h-4" />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-[var(--color-ink)] flex items-center space-x-2">
                    <span>{section.title}</span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] bg-dark-800 text-emerald-400 border border-dark-700 font-mono">
                      {section.items.length} roles
                    </span>
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">{section.subtitle}</p>
                </div>
              </div>
            </div>

            {/* Opportunities Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
              {section.items.map(opp => (
                <div 
                  key={opp.id}
                  className="rounded-xl p-4 bg-dark-800/90 hover:bg-dark-800 border border-dark-700/80 hover:border-dark-600 transition flex flex-col justify-between group"
                >
                  <div>
                    {/* Top Pill / Badge row */}
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className="text-[10px] font-bold text-slate-400  truncate">
                        {opp.company_name}
                      </span>
                      <div className="flex items-center space-x-1.5 flex-shrink-0">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                          {Math.round(opp.match_score)}% Match
                        </span>
                        {opp.deadline_info?.urgency === 'urgent' && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                            {opp.deadline_info.deadline_formatted}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Role Title */}
                    <h3 className="text-xs font-bold text-[var(--color-ink)] line-clamp-1">
                      <button 
                        type="button"
                        onClick={() => onViewDetail(opp.id)}
                        className="text-left group-hover:text-emerald-400 cursor-pointer transition focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-emerald-500 rounded"
                        title={opp.title}
                      >
                        {opp.title}
                      </button>
                    </h3>

                    {/* Project Connection Badge if based on project */}
                    {opp.based_on_project && (
                      <div className="mt-2 p-2 rounded-lg bg-purple-950/30 border border-purple-500/30 text-[11px] text-emerald-300">
                        <div className="flex items-center space-x-1.5 font-semibold text-emerald-300">
                          <FolderGit2 className="w-3.5 h-3.5" />
                          <span>Based on project: {opp.based_on_project.project_title}</span>
                        </div>
                        <p className="text-[10px] text-slate-300 mt-0.5 line-clamp-2">
                          Matches {opp.based_on_project.matching_tech.join(', ')} from your verified code.
                        </p>
                      </div>
                    )}

                    {/* Meta row */}
                    <div className="flex flex-wrap items-center gap-2 mt-2 text-[11px] text-slate-400">
                      <span className="inline-flex items-center space-x-1">
                        <MapPin className="w-3 h-3 text-slate-500" />
                        <span>{opp.normalized_location || opp.location}</span>
                      </span>
                      {opp.stipend_text && (
                        <span className="inline-flex items-center space-x-1 text-emerald-400 font-medium">
                          <DollarSign className="w-3 h-3" />
                          <span>{opp.stipend_text}</span>
                        </span>
                      )}
                      <span className="capitalize px-1.5 py-0.2 rounded bg-dark-700/60 text-slate-300 text-[10px]">
                        {opp.workplace_type}
                      </span>
                    </div>

                    {/* Why it matches highlight */}
                    {opp.why_it_matches && opp.why_it_matches.length > 0 && (
                      <p className="mt-2 text-[11px] text-slate-300 line-clamp-2 italic bg-dark-900/60 p-2 rounded-lg border border-dark-750">
                        "{opp.why_it_matches[0]}"
                      </p>
                    )}

                    {/* Matching skills preview */}
                    {opp.matching_skills && opp.matching_skills.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {opp.matching_skills.slice(0, 3).map((sk, idx) => (
                          <span 
                            key={idx}
                            className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-950/40 text-emerald-300 border border-emerald-500/30 flex items-center space-x-1"
                          >
                            <CheckCircle2 className="w-2.5 h-2.5" />
                            <span>{sk}</span>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Actions Footer */}
                  <div className="mt-3 pt-2.5 border-t border-dark-750 flex items-center justify-between gap-1.5">
                    <div className="flex items-center space-x-1.5">
                      <button
                        type="button"
                        onClick={() => onPrepareApply(opp.id)}
                        className="px-2.5 py-1 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-[11px] font-bold flex items-center space-x-1 transition min-h-[24px] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-emerald-500"
                      >
                        <Send className="w-3 h-3" aria-hidden="true" />
                        <span>Apply</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => onTailorResume(opp.id)}
                        aria-label="Create tailored resume"
                        className="p-1 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-400 border border-emerald-500/30 text-[11px] font-semibold transition min-h-[24px] min-w-[24px] flex items-center justify-center focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-emerald-500"
                        title="Create tailored resume"
                      >
                        <FileText className="w-3.5 h-3.5" aria-hidden="true" />
                      </button>

                      <button
                        type="button"
                        onClick={() => onViewDetail(opp.id)}
                        className="px-2 py-1 rounded-lg bg-dark-700 hover:bg-dark-600 text-slate-300 text-[11px] font-medium transition min-h-[24px] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-emerald-500"
                      >
                        Details
                      </button>
                    </div>

                    <div className="flex items-center space-x-1">
                      <button
                        type="button"
                        onClick={() => onToggleSave(opp.id)}
                        aria-label={opp.is_saved ? 'Remove bookmark' : 'Save opportunity'}
                        className={`p-1 rounded-lg border transition min-h-[24px] min-w-[24px] flex items-center justify-center focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-emerald-500 ${
                          opp.is_saved
                            ? 'bg-amber-500/20 text-amber-400 border-amber-500/40'
                            : 'bg-dark-700/60 hover:bg-dark-700 text-slate-400 border-dark-600'
                        }`}
                        title={opp.is_saved ? 'Remove bookmark' : 'Save opportunity'}
                      >
                        <Bookmark className="w-3.5 h-3.5" aria-hidden="true" />
                      </button>

                      <button
                        type="button"
                        onClick={() => onDismissClick(opp)}
                        aria-label="Dismiss opportunity with feedback"
                        className="p-1 rounded-lg bg-dark-700/60 hover:bg-dark-700 text-slate-400 hover:text-rose-400 border border-dark-600 transition min-h-[24px] min-w-[24px] flex items-center justify-center focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-emerald-500"
                        title="Dismiss with feedback"
                      >
                        <X className="w-3.5 h-3.5" aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
};
