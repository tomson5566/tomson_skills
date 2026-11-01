'use client';

import { useMemo, useState } from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  FileWarning,
  FileLock2,
  Activity,
  FolderSearch,
  ScrollText,
  ChevronDown,
  ChevronRight,
  Wrench,
  Info,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { ScanFinding, ScanReport } from '@/lib/scanner/engine';

const RISK_META = {
  infected: {
    label: '确认感染',
    className: 'bg-red-600 text-white',
    icon: ShieldAlert,
    bannerClass: 'border-red-300 bg-red-50',
    textClass: 'text-red-700',
  },
  suspicious: {
    label: '存在可疑迹象',
    className: 'bg-amber-500 text-white',
    icon: AlertTriangle,
    bannerClass: 'border-amber-300 bg-amber-50',
    textClass: 'text-amber-700',
  },
  clean: {
    label: '未发现威胁',
    className: 'bg-emerald-600 text-white',
    icon: ShieldCheck,
    bannerClass: 'border-emerald-300 bg-emerald-50',
    textClass: 'text-emerald-700',
  },
} as const;

const FINDING_TYPE_META: Record<
  ScanFinding['type'],
  { label: string; icon: typeof FileWarning; hint: string }
> = {
  ransom_note: {
    label: '勒索信',
    icon: ScrollText,
    hint: '目录中存在勒索信文件，是勒索软件已完成加密并索要赎金的直接证据。',
  },
  ransom_note_content: {
    label: '勒索信内容',
    icon: ScrollText,
    hint: '文件名可能已被篡改，但文件内容含勒索软件标识，确认是勒索信。',
  },
  encrypted_file: {
    label: '加密文件',
    icon: FileLock2,
    hint: '文件名后缀命中已知勒索软件家族的特征库，文件很可能已被加密。',
  },
  high_entropy: {
    label: '高熵文件',
    icon: Activity,
    hint: '文档类文件的熵值异常升高（接近随机数据）且不是已知压缩容器格式，疑似内容已被加密。',
  },
  partial_encryption: {
    label: '部分加密',
    icon: FileLock2,
    hint: '只有文件头部被加密、尾部仍是明文，符合 C3RB3R 分级加密策略的特征。',
  },
  suspicious_payload: {
    label: '可疑载荷',
    icon: FileWarning,
    hint: '文件名命中可疑可执行文件特征，可能被用于二次入侵或横向移动。',
  },
  mass_modification: {
    label: '批量修改',
    icon: FolderSearch,
    hint: '短时间内大量文件被修改，符合勒索软件批量加密的行为特征。',
  },
};

/** 每类威胁的处置建议 */
const REMEDIATION: Record<ScanFinding['type'], string[]> = {
  ransom_note: [
    '立即断网隔离该设备，不要重启、不要删除任何文件。',
    '保留勒索信原文与现场快照，用于取证与溯源。',
    '从离线备份或存储快照恢复数据，恢复前先确认备份本身未被污染。',
    '重装操作系统前先导出业务数据，切勿直接覆盖安装。',
  ],
  ransom_note_content: [
    '文件名可能已被篡改，但内容指纹确认是勒索信，按感染事件处理。',
    '立即断网隔离该设备，不要重启、不要删除任何文件。',
    '保留勒索信原文与现场快照，用于取证与溯源。',
    '从离线备份或存储快照恢复数据，恢复前先确认备份本身未被污染。',
  ],
  encrypted_file: [
    '确认受影响文件的范围，优先恢复核心业务目录。',
    '不要尝试用勒索软件自带的解密工具，样本可能不完整。',
    '排查入侵路径：群晖漏洞、WebDAV/CVS 暴露的旧版本、弱口令账号。',
    '修复后关闭对外暴露的管理端口与文件共享服务。',
  ],
  partial_encryption: [
    '这是最难识别的形态：文件能打开但头部已损坏，务必优先恢复这类文件。',
    '部分加密意味着数据可能仍可部分恢复，不要直接丢弃原文件。',
    '恢复前先用另一台设备验证文件实际可读性，确认损坏范围。',
    '同时排查是否还有同目录下的其他文件被同样处理。',
  ],
  high_entropy: [
    '工具已排除压缩包/二进制容器等天然高熵格式，剩余项熵值异常需重点核实。',
    '逐个打开可疑文件确认内容是否可读，不可读基本可判定已被加密。',
    '若确认被加密，按勒索软件事件流程处置。',
    '确认误报时，可把对应扩展名加入熵值检测黑名单。',
  ],
  suspicious_payload: [
    '人工核实文件来源与用途，确认是否为业务必需。',
    '非必需的可执行文件应隔离并留存哈希用于溯源。',
    '检查该文件是否被计划任务或启动项引用。',
  ],
  mass_modification: [
    '对照业务变更记录，确认这批修改是否为本人操作。',
    '若非本人操作，立即按感染事件处理。',
    '检查是否存在异常账号登录与计划任务。',
  ],
};

interface FindingsPanelProps {
  findings: ScanFinding[];
  report: ScanReport | null;
  /** 扫描是否仍在进行 */
  running: boolean;
  /** 扫描是否被中止（此时没有最终报告） */
  aborted: boolean;
}

export function FindingsPanel({
  findings,
  report,
  running,
  aborted,
}: FindingsPanelProps) {
  const [severityFilter, setSeverityFilter] = useState<'all' | 'critical' | 'warning'>(
    'all',
  );
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [showRemediation, setShowRemediation] = useState(true);

  const criticalCount = findings.filter((f) => f.severity === 'critical').length;
  const warningCount = findings.filter((f) => f.severity === 'warning').length;

  // 按类型分组，便于用户快速理解「发现了什么」
  const grouped = useMemo(() => {
    const filtered =
      severityFilter === 'all'
        ? findings
        : findings.filter((f) => f.severity === severityFilter);
    const map = new Map<ScanFinding['type'], ScanFinding[]>();
    for (const f of filtered) {
      const list = map.get(f.type) ?? [];
      list.push(f);
      map.set(f.type, list);
    }
    return Array.from(map.entries());
  }, [findings, severityFilter]);

  const riskMeta = report
    ? RISK_META[report.riskLevel]
    : criticalCount > 0
      ? RISK_META.infected
      : warningCount > 0
        ? RISK_META.suspicious
        : null;

  const toggle = (idx: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  // 没有任何发现时，不展示此面板
  if (findings.length === 0 && !report) return null;

  return (
    <div className="space-y-4">
      <Separator />
      {/* ---------- 结论横幅 ---------- */}
      <div
        className={`rounded-lg border p-4 ${
          riskMeta
            ? riskMeta.bannerClass
            : 'border-slate-200 bg-slate-50'
        }`}
      >
        <div
          className={`flex items-start gap-3 ${
            riskMeta ? riskMeta.textClass : 'text-slate-700'
          }`}
        >
          {riskMeta ? (
            <riskMeta.icon className="size-6 shrink-0 mt-0.5" />
          ) : (
            <Info className="size-6 shrink-0 mt-0.5" />
          )}
          <div className="space-y-1 min-w-0">
            <div className="font-semibold text-base flex items-center gap-2 flex-wrap">
              {riskMeta ? riskMeta.label : '扫描已中止'}
              <span className="font-mono text-xs font-normal opacity-70">
                {report ? (
                  <>
                    耗时 {(report.durationMs / 1000).toFixed(1)}s ·{' '}
                    {report.stats.filesScanned} 文件 · 近1h修改{' '}
                    {report.stats.recentModifiedLastHour} · 近24h修改{' '}
                    {report.stats.recentModifiedLast24h}
                  </>
                ) : (
                  <>已扫描 {findings.length} 项威胁，发现即列出</>
                )}
              </span>
              {running && (
                <Badge variant="secondary" className="font-normal">
                  扫描进行中…
                </Badge>
              )}
              {aborted && (
                <Badge
                  variant="outline"
                  className="border-amber-300 text-amber-700 font-normal"
                >
                  扫描已中止，以下为中止前发现
                </Badge>
              )}
            </div>
            <p className="text-sm leading-6">
              {report
                ? report.summary
                : '扫描被手动中止，以下威胁项为中止前已确认的结果，可据此先行处置。'}
            </p>
          </div>
        </div>
      </div>

      {/* ---------- 威胁明细 ---------- */}
      {findings.length > 0 && (
        <div className="rounded-lg border border-slate-200 overflow-hidden">
          <div className="bg-slate-50 px-4 py-2.5 flex items-center justify-between gap-3 flex-wrap">
            <span className="text-sm font-medium text-slate-700">
              威胁明细（{findings.length}）
            </span>
            <div className="flex items-center gap-1.5">
              <FilterButton
                active={severityFilter === 'all'}
                onClick={() => setSeverityFilter('all')}
              >
                全部 {findings.length}
              </FilterButton>
              <FilterButton
                active={severityFilter === 'critical'}
                onClick={() => setSeverityFilter('critical')}
                tone="critical"
              >
                高危 {criticalCount}
              </FilterButton>
              <FilterButton
                active={severityFilter === 'warning'}
                onClick={() => setSeverityFilter('warning')}
                tone="warning"
              >
                可疑 {warningCount}
              </FilterButton>
            </div>
          </div>

          <div className="divide-y divide-slate-100">
            {grouped.map(([type, list]) => {
              const meta = FINDING_TYPE_META[type];
              const groupKey = list[0]?.path ?? type;
              return (
                <div key={groupKey}>
                  {/* 分组标题 */}
                  <div className="px-4 py-2 bg-slate-50/60 flex items-center gap-2 border-b border-slate-100">
                    <meta.icon
                      className={`size-4 shrink-0 ${
                        list.some((f) => f.severity === 'critical')
                          ? 'text-red-600'
                          : 'text-amber-600'
                      }`}
                    />
                    <span className="text-sm font-medium text-slate-700">
                      {meta.label}
                    </span>
                    <Badge variant="secondary" className="font-normal">
                      {list.length} 项
                    </Badge>
                    <span className="text-xs text-slate-500 truncate">
                      {meta.hint}
                    </span>
                  </div>

                  {list.map((f) => {
                    const globalIdx = findings.indexOf(f);
                    const isOpen = expanded.has(globalIdx);
                    const advice = REMEDIATION[f.type];
                    return (
                      <div key={globalIdx} className="bg-white">
                        <button
                          type="button"
                          onClick={() => toggle(globalIdx)}
                          className="w-full text-left px-4 py-3 flex items-start gap-3 hover:bg-slate-50 transition-colors"
                        >
                          <span className="mt-0.5 shrink-0 text-slate-400">
                            {isOpen ? (
                              <ChevronDown className="size-4" />
                            ) : (
                              <ChevronRight className="size-4" />
                            )}
                          </span>
                          <div className="min-w-0 flex-1 space-y-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <Badge
                                variant="outline"
                                className={
                                  f.severity === 'critical'
                                    ? 'border-red-300 text-red-700'
                                    : 'border-amber-300 text-amber-700'
                                }
                              >
                                {f.severity === 'critical' ? '高危' : '可疑'}
                              </Badge>
                              <span className="font-mono text-xs text-slate-600 break-all">
                                {f.path}
                              </span>
                              {f.entropy !== undefined && (
                                <Badge variant="secondary" className="font-normal">
                                  熵值 {f.entropy}
                                </Badge>
                              )}
                              {f.headEntropy !== undefined &&
                                f.tailEntropy !== undefined && (
                                  <Badge
                                    variant="outline"
                                    className="border-red-300 text-red-700 font-normal"
                                  >
                                    头 {f.headEntropy} / 尾 {f.tailEntropy}
                                  </Badge>
                                )}
                            </div>
                            <p className="text-sm text-slate-600">{f.detail}</p>
                            {f.family && (
                              <p className="text-xs text-slate-500">
                                归属家族：{f.family}
                              </p>
                            )}
                          </div>
                        </button>

                        {isOpen && (
                          <div className="px-4 pb-4 pl-11">
                            {showRemediation && (
                              <div className="rounded-md bg-slate-50 border border-slate-200 p-3">
                                <div className="flex items-center gap-2 mb-2">
                                  <Wrench className="size-3.5 text-slate-500" />
                                  <span className="text-xs font-medium text-slate-600">
                                    处置建议
                                  </span>
                                </div>
                                <ul className="space-y-1.5">
                                  {advice.map((a, ai) => (
                                    <li
                                      key={ai}
                                      className="text-xs text-slate-600 flex gap-2 leading-5"
                                    >
                                      <span className="text-slate-400 shrink-0">
                                        {ai + 1}.
                                      </span>
                                      <span>{a}</span>
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>

          <div className="px-4 py-2.5 bg-slate-50 border-t border-slate-200">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowRemediation((v) => !v)}
              className="text-xs text-slate-600"
            >
              {showRemediation ? '隐藏处置建议' : '显示处置建议'}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function FilterButton({
  active,
  onClick,
  tone,
  children,
}: {
  active: boolean;
  onClick: () => void;
  tone?: 'critical' | 'warning';
  children: React.ReactNode;
}) {
  const toneClass =
    tone === 'critical'
      ? 'border-red-300 text-red-700'
      : tone === 'warning'
        ? 'border-amber-300 text-amber-700'
        : 'border-slate-300 text-slate-700';
  return (
    <button
      type="button"
      onClick={onClick}
      className={`text-xs px-2 py-1 rounded border transition-colors ${
        active
          ? `${toneClass} bg-white font-medium`
          : 'border-transparent text-slate-500 hover:bg-slate-100'
      }`}
    >
      {children}
    </button>
  );
}

/** 轻量分隔线（避免额外引入 ui/separator 的额外依赖判断） */
function Separator() {
  return <div className="h-px w-full bg-slate-200" />;
}
