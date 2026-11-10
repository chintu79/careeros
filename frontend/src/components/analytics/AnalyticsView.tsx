import React, { useState, useEffect } from 'react';
import {
  GitCommit,
  CheckCircle2,
  X,
  Table as TableIcon,
  ShieldAlert
} from 'lucide-react';
import { SankeyData, SankeyNode, SankeyLink } from '../../types';
import { fetchAnalytics, fetchSankeyData, fetchSourceEfficacyAnalytics } from '../../services/api';
import { CountUp } from '../ui/CountUp';
import { PageHeader, StatTile } from '../ui/PageHeader';

export const AnalyticsView: React.FC = () => {
  const [analytics, setAnalytics] = useState<any>(null);
  const [sankeyData, setSankeyData] = useState<SankeyData | null>(null);
  const [sourceEfficacy, setSourceEfficacy] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Filters & Accessible View Mode
  const [sourceFilter, setSourceFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [selectedNode, setSelectedNode] = useState<SankeyNode | null>(null);
  const [chartViewMode, setChartViewMode] = useState<'diagram' | 'table'>('diagram');

  // loadAll lives inside the effect: its only caller is the effect itself and it
  // captures exactly the two filter inputs the effect subscribes to.
  useEffect(() => {
    const loadAll = async () => {
      setLoading(true);
      try {
        const [anRes, skRes, effRes] = await Promise.all([
          fetchAnalytics(),
          fetchSankeyData(sourceFilter, categoryFilter),
          fetchSourceEfficacyAnalytics().catch(() => [])
        ]);
        setAnalytics(anRes);
        setSankeyData(skRes);
        setSourceEfficacy(effRes || []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadAll();
  }, [sourceFilter, categoryFilter]);

  if (loading && !analytics) {
    return (
      <div className="flex flex-col items-center gap-3 py-24 text-slate-400">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent" />
        <p className="text-[12px]">Loading career analytics…</p>
      </div>
    );
  }

  const summary = analytics?.summary || {};

  // Simple layout computation for SVG Sankey nodes & links
  const renderSankeySvg = () => {
    if (!sankeyData || sankeyData.empty || !sankeyData.nodes || sankeyData.nodes.length === 0) {
      return (
        <div className="rounded-lg border border-dashed border-white/[0.09] p-10 text-center">
          <GitCommit className="mx-auto mb-2 h-8 w-8 text-slate-600" />
          <h4 className="text-[13px] font-medium text-[var(--color-ink)]">Insufficient Application Flow Data</h4>
          <p className="mx-auto mt-1 max-w-sm text-[12px] leading-relaxed text-slate-500">
            {sankeyData?.message || "No stage transitions recorded yet. Move opportunities between tracking stages to see real database-grounded flow."}
          </p>
        </div>
      );
    }

    const svgWidth = 860;
    const svgHeight = 250;
    const nodeWidth = 138;
    const nodeHeight = 38;

    // Partition nodes into sequential columns
    const stageColumns: Record<string, number> = {
      "discovered": 0,
      "saved": 0,
      "ready_to_apply": 1,
      "applied": 2,
      "recruiter_response": 3,
      "screening": 3,
      "technical_interview": 4,
      "interviewing": 4,
      "hr_interview": 4,
      "final_round": 4,
      "offer": 5,
      "offered": 5,
      "rejected": 5,
      "withdrawn": 5,
      "no_response": 5
    };

    const maxCol = 5;
    const colStep = (svgWidth - nodeWidth - 40) / maxCol;

    const columnBuckets: Record<number, SankeyNode[]> = {};
    sankeyData.nodes.forEach(node => {
      const col = stageColumns[node.stage_key] ?? 2;
      columnBuckets[col] = columnBuckets[col] || [];
      columnBuckets[col].push(node);
    });

    const nodePositions: Record<number, { x: number; y: number }> = {};
    Object.entries(columnBuckets).forEach(([colStr, colNodes]) => {
      const col = Number(colStr);
      const x = 20 + col * colStep;
      const count = colNodes.length;
      const spacing = svgHeight / (count + 1);
      colNodes.forEach((node, idx) => {
        const y = spacing * (idx + 1) - nodeHeight / 2;
        nodePositions[node.id] = { x, y };
      });
    });

    return (
      <figure className="overflow-x-auto rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3">
        <figcaption className="sr-only">Interactive Application Pipeline Flow Diagram</figcaption>
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="h-auto w-full min-w-[720px]"
        >
          <title>Application Pipeline Movement Diagram</title>
          <desc>Visual diagram of candidate application stage conversions</desc>

          {/* Links / Flow Ribbons */}
          {sankeyData.links.map((link, idx) => {
            const srcPos = nodePositions[link.source];
            const tgtPos = nodePositions[link.target];
            if (!srcPos || !tgtPos || link.source === link.target) return null;

            const x0 = srcPos.x + nodeWidth;
            const y0 = srcPos.y + nodeHeight / 2;
            const x1 = tgtPos.x;
            const y1 = tgtPos.y + nodeHeight / 2;
            const midX = (x0 + x1) / 2;

            const strokeWidth = Math.max(1.5, Math.min(10, link.value * 0.9));
            return (
              <path
                key={idx}
                d={`M ${x0} ${y0} C ${midX} ${y0}, ${midX} ${y1}, ${x1} ${y1}`}
                fill="none"
                stroke="var(--color-accent)"
                strokeOpacity={0.28}
                strokeWidth={strokeWidth}
                className="cursor-pointer transition-opacity hover:opacity-100"
              >
                <title>{`${link.source_name} → ${link.target_name}: ${link.value} movement(s)`}</title>
              </path>
            );
          })}

          {/* Nodes */}
          {sankeyData.nodes.map(node => {
            const pos = nodePositions[node.id];
            if (!pos) return null;
            const isSelected = selectedNode?.id === node.id;
            return (
              <g
                key={node.id}
                role="button"
                tabIndex={0}
                transform={`translate(${pos.x}, ${pos.y})`}
                onClick={() => setSelectedNode(node)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setSelectedNode(node);
                  }
                }}
                className="cursor-pointer group outline-none focus:outline-none"
              >
                <rect
                  width={nodeWidth}
                  height={nodeHeight}
                  rx={6}
                  className={`transition-colors duration-150 ${
                    isSelected
                      ? 'fill-emerald-400/10 stroke-emerald-400'
                      : 'fill-[var(--color-paper-2)] stroke-white/[0.10] hover:stroke-emerald-400/50 group-focus:stroke-emerald-400'
                  }`}
                  strokeWidth={1}
                />
                <text
                  x={10}
                  y={16}
                  className="fill-slate-200 text-[11px] font-medium select-none"
                >
                  {node.name}
                </text>
                <text
                  x={10}
                  y={29}
                  className="fill-emerald-300/90 text-[10px] font-mono select-none"
                >
                  {node.count} records
                </text>
              </g>
            );
          })}
        </svg>

        <p className="mt-1 text-center text-[10px] text-slate-500">
          Select a stage to inspect the applications that reached it.
        </p>
      </figure>
    );
  };

  // Accessible Tabular Alternative for Screen Readers & Non-Mouse Users
  const renderSankeyTable = () => {
    if (!sankeyData || sankeyData.empty || !sankeyData.nodes || sankeyData.nodes.length === 0) {
      return (
        <div className="rounded-lg border border-dashed border-white/[0.09] p-8 text-center text-[12px] text-slate-500">
          No application stage data recorded.
        </div>
      );
    }

    return (
      <div className="overflow-x-auto rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-4">
        <table className="w-full border-collapse text-left text-[12px]">
          <caption className="mb-2 text-left text-[13px] font-medium text-[var(--color-ink)]">
            Application Pipeline Stages & Conversion Matrix
          </caption>
          <thead>
            <tr className="border-b border-white/[0.07] text-[10px] font-medium text-slate-500">
              <th scope="col" className="py-2.5 px-3">Pipeline Stage</th>
              <th scope="col" className="py-2.5 px-3">Stage Key</th>
              <th scope="col" className="py-2.5 px-3 text-right">Applications Count</th>
              <th scope="col" className="py-2.5 px-3">Active Flows Out</th>
              <th scope="col" className="px-3 py-2.5 text-center">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.05]">
            {sankeyData.nodes.map((node) => {
              const outgoingLinks = sankeyData.links.filter(l => l.source === node.id);
              return (
                <tr key={node.id} className="transition-colors hover:bg-white/[0.02]">
                  <th scope="row" className="px-3 py-2.5 font-medium text-[var(--color-ink)]">
                    {node.name}
                  </th>
                  <td className="px-3 py-2.5 font-mono text-[11px] text-slate-500">
                    {node.stage_key}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono font-medium text-emerald-300">
                    {node.count}
                  </td>
                  <td className="px-3 py-2.5 text-slate-300">
                    {outgoingLinks.length === 0 ? (
                      <span className="text-slate-500">Terminal stage</span>
                    ) : (
                      outgoingLinks.map((l, i) => (
                        <span key={i} className="mr-2 inline-block rounded border border-white/[0.07] bg-white/[0.03] px-1.5 py-0.5 text-[10px]">
                          → {l.target_name}: <strong>{l.value}</strong>
                        </span>
                      ))
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <button
                      type="button"
                      onClick={() => setSelectedNode(node)}
                      aria-label={`Inspect ${node.name} applications (${node.count})`}
                      className="rounded border border-white/[0.09] px-2 py-1 text-[11px] font-medium text-slate-300 transition-colors hover:bg-white/[0.05] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
                    >
                      Inspect
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        eyebrow="Intelligence"
        title="Career Insights"
        description="Where your pipeline actually moves , conversion, source quality and the stages that stall."
      />

      {/* KPI Cards Banner */}
      <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-4">
        <StatTile
          label="Total opportunities"
          value={<CountUp to={summary.total_discovered || 0} duration={1.0} />}
          hint={`+${summary.new_today || 0} added today`}
        />
        <StatTile
          label="Tracked applications"
          value={<CountUp to={summary.applied_count || 0} duration={0.9} />}
          hint="Active pipeline"
        />
        <StatTile
          label="High match"
          value={<CountUp to={summary.high_match_count || 0} duration={1.1} />}
          hint="70% and above"
        />
        <StatTile
          label="Sync reliability"
          value={
            <>
              <CountUp to={summary.sync_reliability_pct || 100} duration={0.9} />%
            </>
          }
          hint={`${summary.duplicates_prevented || 0} duplicates avoided`}
        />
      </div>

      {/* Sankey Diagram Section */}
      <section className="rounded-xl border border-white/[0.07] bg-[var(--color-paper)]">
        <div className="flex flex-col gap-3 border-b border-white/[0.06] px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <h2 className="section-title">Pipeline movement</h2>
            <p className="mt-0.5 text-[12px] text-slate-500">
              Stage transitions recorded in your tracker , no fabricated flows.
            </p>
          </div>

          {/* View Switcher & Filters */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex items-center gap-0.5 rounded-lg border border-white/[0.07] bg-black/20 p-0.5" role="group" aria-label="Pipeline view format">
              <button
                type="button"
                onClick={() => setChartViewMode('diagram')}
                aria-pressed={chartViewMode === 'diagram'}
                className={`inline-flex min-h-[28px] items-center gap-1.5 rounded-[6px] px-2 text-[11px] font-medium transition-colors ${
                  chartViewMode === 'diagram'
                    ? 'bg-white/[0.08] text-[var(--color-ink)]'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <GitCommit className="h-3 w-3" aria-hidden="true" />
                <span>Diagram</span>
              </button>
              <button
                type="button"
                onClick={() => setChartViewMode('table')}
                aria-pressed={chartViewMode === 'table'}
                className={`inline-flex min-h-[28px] items-center gap-1.5 rounded-[6px] px-2 text-[11px] font-medium transition-colors ${
                  chartViewMode === 'table'
                    ? 'bg-white/[0.08] text-[var(--color-ink)]'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <TableIcon className="h-3 w-3" aria-hidden="true" />
                <span>Table</span>
              </button>
            </div>

            <select
              value={sourceFilter}
              onChange={e => setSourceFilter(e.target.value)}
              aria-label="Filter pipeline by source platform"
              className="input-base min-h-[32px] w-auto py-1 text-[11px]"
            >
              <option value="all">All sources</option>
              <option value="internshala">Internshala</option>
              <option value="linkedin">LinkedIn</option>
              <option value="lever">Lever</option>
              <option value="greenhouse">Greenhouse</option>
              <option value="ashby">Ashby</option>
            </select>

            <select
              value={categoryFilter}
              onChange={e => setCategoryFilter(e.target.value)}
              aria-label="Filter pipeline by job category"
              className="input-base min-h-[32px] w-auto py-1 text-[11px]"
            >
              <option value="all">All categories</option>
              <option value="software_engineering">Software engineering</option>
              <option value="backend">Backend</option>
              <option value="frontend">Frontend</option>
              <option value="ai_ml">AI / ML</option>
            </select>
          </div>
        </div>

        <div className="p-3 sm:p-4">
          {chartViewMode === 'diagram' ? renderSankeySvg() : renderSankeyTable()}
        </div>

        {/* Selected Node Details Drawer */}
        {selectedNode && (
          <div className="mx-3 mb-3 rounded-lg border border-emerald-400/25 bg-emerald-400/[0.04] p-3.5 space-y-3 sm:mx-4 sm:mb-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                <h4 className="text-[11px] font-medium text-slate-300">
                  Inspecting Stage: {selectedNode.name} ({selectedNode.count} records)
                </h4>
              </div>
              <button
                type="button"
                onClick={() => setSelectedNode(null)}
                aria-label="Close stage details"
                className="rounded p-1 text-slate-500 transition-colors hover:bg-white/[0.05] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
              >
                <X className="w-4 h-4" aria-hidden="true" />
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
              {selectedNode.applications && selectedNode.applications.map((app, i) => (
                <div key={i} className="rounded-md border border-white/[0.06] bg-[var(--color-paper)] p-2.5">
                  <span className="block truncate text-[12px] font-medium text-[var(--color-ink)]">{app.company_name}</span>
                  <span className="block truncate text-[11px] text-slate-500">{app.job_title}</span>
                  <div className="mt-1 flex items-center justify-between text-[10px]">
                    <span className="font-mono text-emerald-300">{Math.round(app.match_score)}% Match</span>
                    <span className="capitalize text-slate-500">{(app as any).source || 'Direct'}</span>
                  </div>
                </div>
              ))}
              {(!selectedNode.applications || selectedNode.applications.length === 0) && (
                <p className="col-span-full text-[12px] text-slate-500">No individual application details attached.</p>
              )}
            </div>
          </div>
        )}
      </section>

      {/* Discovery Sources & Locations Breakdown */}
      <div className="grid grid-cols-1 gap-2.5 md:grid-cols-2">
        <div className="rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4">
          <span className="text-[11px] font-medium text-slate-400">Opportunities by Source Platform</span>
          <div className="mt-3 space-y-0">
            {analytics?.by_source && analytics.by_source.map((s: any, i: number) => (
              <div key={i} className="flex items-center justify-between border-t border-white/[0.05] py-2 text-[12px] first:border-t-0">
                <span className="capitalize text-slate-300">{s.source}</span>
                <span className="font-mono text-emerald-300 tnum">{s.count}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4">
          <span className="text-[11px] font-medium text-slate-400">Top Discovered Locations</span>
          <div className="mt-3 space-y-0">
            {analytics?.by_location && analytics.by_location.map((l: any, i: number) => (
              <div key={i} className="flex items-center justify-between border-t border-white/[0.05] py-2 text-[12px] first:border-t-0">
                <span className="text-slate-300">{l.location}</span>
                <span className="font-mono text-slate-300 tnum">{l.count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Source Performance & Efficacy Table */}
      <div className="rounded-xl border border-white/[0.07] bg-[var(--color-paper)]">
        <div className="border-b border-white/[0.06] px-4 py-3.5">
          <div>
            <h3 className="section-title">
              
              <span>Source Performance & Data Quality Efficacy</span>
            </h3>
            <p className="mt-0.5 text-[12px] text-slate-500">
              Transparent conversion, duplicate prevention, and listing freshness across all monitored sources.
            </p>
          </div>
        </div>

        <div className="overflow-x-auto p-4">
          <table className="w-full text-left text-[12px] text-slate-300">
            <thead className="border-b border-white/[0.07] text-[10px] font-medium text-slate-500">
              <tr>
                <th className="py-2.5">Source</th>
                <th className="py-2.5">Status</th>
                <th className="py-2.5">Discovered</th>
                <th className="py-2.5">Active</th>
                <th className="py-2.5">Duplicate Rate</th>
                <th className="py-2.5">Expired Rate</th>
                <th className="py-2.5">Conversion</th>
                <th className="py-2.5">Reliability / Sample</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.05]">
              {sourceEfficacy.map(src => (
                <tr key={src.source_id} className="transition-colors hover:bg-white/[0.02]">
                  <td className="py-2.5 font-medium text-[var(--color-ink)]">{src.source_name}</td>
                  <td className="py-2.5">
                    <span className="rounded border border-white/[0.08] bg-white/[0.03] px-1.5 py-0.5 font-mono text-[10px] capitalize text-slate-400">
                      {src.connection_status}
                    </span>
                  </td>
                  <td className="py-2.5 font-mono tnum">{src.total_discovered}</td>
                  <td className="py-2.5 font-mono font-medium text-emerald-300">{src.active_count}</td>
                  <td className="py-2.5 font-mono text-sky-300">{src.duplicate_rate}%</td>
                  <td className="py-2.5 font-mono text-amber-300">{src.expired_rate}%</td>
                  <td className="py-2.5 font-mono text-emerald-300">{src.conversion_rate}%</td>
                  <td className="py-2.5">
                    {src.has_sufficient_sample ? (
                      <span className="flex items-center gap-1 text-[10px] font-medium text-emerald-300">
                        <CheckCircle2 className="w-3 h-3 inline mr-1" />
                        <span>Verified Sample</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded border border-amber-400/20 bg-amber-400/[0.06] px-1.5 py-0.5 text-[10px] font-medium text-amber-300">
                        <ShieldAlert className="w-3 h-3 inline mr-1" />
                        <span>Preliminary (&lt;5 jobs)</span>
                      </span>
                    )}
                  </td>
                </tr>
              ))}
              {sourceEfficacy.length === 0 && (
                <tr>
                  <td colSpan={8} className="py-6 text-center text-[12px] text-slate-500">
                    No source efficacy metrics recorded yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
