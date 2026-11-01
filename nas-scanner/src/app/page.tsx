import { ShieldAlert, Radar, Bug } from 'lucide-react';
import { ScanPanel } from '@/components/scanner/scan-panel';
import { DsmChecker } from '@/components/scanner/dsm-checker';
import { Badge } from '@/components/ui/badge';
import { RANSOMWARE_FAMILIES } from '@/lib/scanner/signatures';

export default function Home() {
  return (
    <div className="min-h-screen bg-[#F7F8FA]">
      {/* 顶部栏 */}
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-5 flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-[#1E3A5F] text-white">
            <Radar className="size-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-900 leading-tight">
              NAS 勒索软件威胁扫描器
            </h1>
            <p className="text-xs text-muted-foreground font-mono">
              Ransomware Threat Scanner for NAS · IOC + Entropy + Behavior
            </p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 space-y-6">
        {/* 威胁情报横幅 */}
        <div className="rounded-lg border border-red-200 bg-white p-4 flex items-start gap-3">
          <ShieldAlert className="size-5 text-red-600 shrink-0 mt-0.5" />
          <div className="text-sm leading-6 text-slate-700">
            <span className="font-semibold text-slate-900">在野威胁情报：</span>
            C3RB3R（Cerber 变种）勒索软件正通过 DSM 漏洞
            <span className="font-mono text-red-700"> CVE-2026-13639 / CVE-2026-13684</span>
            （CVSS 9.8，未授权远程读写）大规模加密群晖设备。加密文件追加
            <span className="font-mono"> .L0CK3D </span>
            后缀并留下 <span className="font-mono">read-me3.txt</span> 勒索信。
            修复基线：DSM 7.4-90075 / 7.3.2-86009-4 / 7.2.2-72806-9 / 7.2.1-69057 Update 12 及以上。
          </div>
        </div>

        {/* 主区域 */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 items-start">
          <div className="lg:col-span-3">
            <ScanPanel />
          </div>
          <div className="lg:col-span-2">
            <DsmChecker />
          </div>
        </div>

        {/* 特征库 */}
        <section className="rounded-lg border border-slate-200 bg-white">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2">
            <Bug className="size-4 text-[#1E3A5F]" />
            <h2 className="font-semibold text-slate-900">内置威胁特征库</h2>
            <span className="text-xs text-muted-foreground">
              覆盖 {RANSOMWARE_FAMILIES.length} 个勒索软件家族 · 基于公开威胁情报
            </span>
          </div>
          <div className="divide-y divide-slate-100">
            {RANSOMWARE_FAMILIES.map((f) => (
              <div key={f.id} className="px-4 py-3 space-y-1.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-sm text-slate-900">{f.name}</span>
                  <Badge
                    variant="outline"
                    className={
                      f.severity === 'critical'
                        ? 'border-red-300 text-red-700'
                        : 'border-amber-300 text-amber-700'
                    }
                  >
                    {f.severity === 'critical' ? '在野爆发' : '高危'}
                  </Badge>
                  <span className="text-xs text-muted-foreground">{f.reference}</span>
                </div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  {f.extensions.slice(0, 8).map((ext) => (
                    <code
                      key={ext}
                      className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700"
                    >
                      *{ext}
                    </code>
                  ))}
                  {f.extensions.length > 8 && (
                    <span className="text-xs text-muted-foreground">
                      等 {f.extensions.length} 个后缀
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>

        <footer className="pb-8 text-center text-xs text-muted-foreground">
          本工具基于公开威胁情报与文件系统统计学特征进行检测，只读扫描不修改任何文件。
          检测结果供参考，不能替代专业安全应急响应。
        </footer>
      </main>
    </div>
  );
}
