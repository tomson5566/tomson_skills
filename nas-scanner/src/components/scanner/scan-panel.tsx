'use client';

import { useCallback, useRef, useState } from 'react';
import {
  Radar,
  Play,
  Square,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  Server,
  HardDrive,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Separator } from '@/components/ui/separator';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Checkbox } from '@/components/ui/checkbox';
import type {
  ScanEvent,
  ScanFinding,
  ScanProgress,
  ScanReport,
} from '@/lib/scanner/engine';
import { FindingsPanel } from './findings-panel';

type ScanStatus = 'idle' | 'running' | 'done' | 'error';

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

export function ScanPanel() {
  const [mode, setMode] = useState<'local' | 'smb'>('smb');
  const [path, setPath] = useState('/tmp/mock-nas');
  const [host, setHost] = useState('');
  const [share, setShare] = useState('homes');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [domain, setDomain] = useState('SAMBA');
  const [enableEntropy, setEnableEntropy] = useState(true);
  const [maxDepth, setMaxDepth] = useState('12');

  const [status, setStatus] = useState<ScanStatus>('idle');
  const [logs, setLogs] = useState<string[]>([]);
  const [progress, setProgress] = useState<ScanProgress | null>(null);
  const [findings, setFindings] = useState<ScanFinding[]>([]);
  const [report, setReport] = useState<ScanReport | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [aborted, setAborted] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const logBoxRef = useRef<HTMLDivElement | null>(null);

  const appendLog = useCallback((line: string) => {
    setLogs((prev) => {
      const next = [...prev, line];
      return next.length > 300 ? next.slice(next.length - 300) : next;
    });
    requestAnimationFrame(() => {
      logBoxRef.current?.scrollTo({ top: logBoxRef.current.scrollHeight });
    });
  }, []);

  const stopScan = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const startScan = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus('running');
    setLogs([]);
    setProgress(null);
    setFindings([]);
    setReport(null);
    setErrorMsg('');
    setAborted(false);

    const payload =
      mode === 'local'
        ? { mode, path, enableEntropy, maxDepth: parseInt(maxDepth, 10) || 12 }
        : {
            mode,
            host: host.trim(),
            share: share.trim(),
            username: username.trim(),
            password,
            domain: domain.trim(),
            enableEntropy,
            maxDepth: parseInt(maxDepth, 10) || 12,
          };

    try {
      const res = await fetch('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      if (!res.ok || !res.body) {
        const text = await res.text().catch(() => '');
        throw new Error(text || `请求失败（HTTP ${res.status}）`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() ?? '';
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith('data:')) continue;
          let event: ScanEvent;
          try {
            event = JSON.parse(line.slice(5).trim()) as ScanEvent;
          } catch {
            continue;
          }
          if (event.type === 'progress') {
            setProgress(event.data);
          } else if (event.type === 'finding') {
            setFindings((prev) => [...prev, event.data]);
          } else if (event.type === 'log') {
            appendLog(event.data);
          } else if (event.type === 'done') {
            setReport(event.data);
            setStatus('done');
          } else if (event.type === 'error') {
            setErrorMsg(event.data);
            setStatus('error');
          }
        }
      }
      setStatus((s) => (s === 'running' ? 'done' : s));
    } catch (err) {
      if ((err as Error).name === 'AbortError') {
        appendLog('扫描已被手动中止');
        setStatus('idle');
        setAborted(true);
      } else {
        setErrorMsg(err instanceof Error ? err.message : String(err));
        setStatus('error');
      }
    }
  }, [mode, path, host, share, username, password, domain, enableEntropy, maxDepth, appendLog]);

  const running = status === 'running';
  const riskMeta = report ? RISK_META[report.riskLevel] : null;

  return (
    <Card className="border-slate-200">
      <CardHeader>
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <CardTitle className="flex items-center gap-2 text-[#1E3A5F]">
              <Radar className="size-5" />
              威胁扫描
            </CardTitle>
            <CardDescription>
              通过 SMB 直连 NAS 共享目录，或扫描已挂载到本机的目录。扫描过程只读，不会修改任何文件。
            </CardDescription>
          </div>
          {report && riskMeta && (
            <Badge className={riskMeta.className}>{riskMeta.label}</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* ---------- 配置区 ---------- */}
        <div className="space-y-4">
          <RadioGroup
            value={mode}
            onValueChange={(v) => setMode(v as 'local' | 'smb')}
            className="flex flex-wrap gap-4"
            disabled={running}
          >
            <div className="flex items-center gap-2">
              <RadioGroupItem value="smb" id="mode-smb" />
              <Label htmlFor="mode-smb" className="flex items-center gap-1.5 cursor-pointer">
                <Server className="size-4" /> SMB 远程连接 NAS
              </Label>
            </div>
            <div className="flex items-center gap-2">
              <RadioGroupItem value="local" id="mode-local" />
              <Label htmlFor="mode-local" className="flex items-center gap-1.5 cursor-pointer">
                <HardDrive className="size-4" /> 本机目录（已挂载的共享）
              </Label>
            </div>
          </RadioGroup>

          {mode === 'smb' ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="smb-host">NAS 地址</Label>
                <Input
                  id="smb-host"
                  placeholder="192.168.1.10"
                  value={host}
                  onChange={(e) => setHost(e.target.value)}
                  disabled={running}
                  className="font-mono"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="smb-share">共享文件夹</Label>
                <Input
                  id="smb-share"
                  placeholder="homes / photo / docs"
                  value={share}
                  onChange={(e) => setShare(e.target.value)}
                  disabled={running}
                  className="font-mono"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="smb-user">账号</Label>
                <Input
                  id="smb-user"
                  placeholder="只读权限账号即可"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  disabled={running}
                  autoComplete="off"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="smb-pass">密码</Label>
                <Input
                  id="smb-pass"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={running}
                  autoComplete="new-password"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="smb-domain">NTLM 域</Label>
                <Input
                  id="smb-domain"
                  placeholder="群晖通常为 SAMBA"
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  disabled={running}
                  autoComplete="off"
                  className="font-mono"
                />
                <p className="text-xs text-muted-foreground">
                  群晖默认为 SAMBA；部分环境为 WORKGROUP，留空表示不发送域
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-1.5">
              <Label htmlFor="local-path">本机目录路径</Label>
              <Input
                id="local-path"
                placeholder="/mnt/nas 或挂载点路径"
                value={path}
                onChange={(e) => setPath(e.target.value)}
                disabled={running}
                className="font-mono"
              />
              <p className="text-xs text-muted-foreground">
                本演示环境内置了一个模拟受感染目录 /tmp/mock-nas，可直接体验扫描效果
              </p>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-6">
            <div className="flex items-center gap-2">
              <Checkbox
                id="entropy"
                checked={enableEntropy}
                onCheckedChange={(v) => setEnableEntropy(v === true)}
                disabled={running}
              />
              <Label htmlFor="entropy" className="cursor-pointer text-sm">
                启用熵值分析（检测文档类文件是否被加密）
              </Label>
            </div>
            <div className="flex items-center gap-2">
              <Label htmlFor="maxDepth" className="text-sm whitespace-nowrap">
                最大目录深度
              </Label>
              <Input
                id="maxDepth"
                type="number"
                min={1}
                max={30}
                value={maxDepth}
                onChange={(e) => setMaxDepth(e.target.value)}
                disabled={running}
                className="w-20 font-mono"
              />
            </div>
          </div>

          <div className="flex gap-3">
            {running ? (
              <Button variant="destructive" onClick={stopScan}>
                <Square className="size-4" />
                中止扫描
              </Button>
            ) : (
              <Button
                onClick={startScan}
                className="bg-[#1E3A5F] hover:bg-[#16294a]"
                disabled={mode === 'smb' ? !host.trim() || !share.trim() : !path.trim()}
              >
                <Play className="size-4" />
                开始扫描
              </Button>
            )}
          </div>
        </div>

        {/* ---------- 进度区 ---------- */}
        {(running || progress) && (
          <>
            <Separator />
            <div className="space-y-3">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <StatCard label="已扫描文件" value={progress?.filesScanned ?? 0} />
                <StatCard label="已遍历目录" value={progress?.dirsScanned ?? 0} />
                <StatCard label="熵值抽样" value={progress?.entropySampled ?? 0} />
                <StatCard
                  label="发现威胁项"
                  value={findings.length}
                  highlight={findings.length > 0}
                />
              </div>
              <div
                ref={logBoxRef}
                className="h-40 overflow-y-auto rounded-md border border-slate-200 bg-slate-950 p-3 font-mono text-xs leading-5 text-slate-200"
              >
                {logs.map((line, i) => (
                  <div key={i}>{line}</div>
                ))}
                {progress && (
                  <div className="text-slate-500 truncate">
                    {running ? '▸ 正在扫描 ' : '▸ 最后位置 '}
                    {progress.currentPath}
                  </div>
                )}
                {running && logs.length === 0 && !progress && (
                  <div className="text-slate-500">连接中…</div>
                )}
              </div>
            </div>
          </>
        )}

        {/* ---------- 错误 ---------- */}
        {status === 'error' && errorMsg && (
          <Alert variant="destructive">
            <AlertTriangle className="size-4" />
            <AlertTitle>扫描失败</AlertTitle>
            <AlertDescription className="font-mono text-xs break-all">
              {errorMsg}
            </AlertDescription>
          </Alert>
        )}

        {/* ---------- 报告与威胁明细 ---------- */}
        <FindingsPanel
          findings={findings}
          report={report}
          running={running}
          aborted={aborted}
        />

      </CardContent>
    </Card>
  );
}

function StatCard({
  label,
  value,
  highlight,
}: {
  label: string;
  value: number;
  highlight?: boolean;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={`mt-1 font-mono text-2xl font-semibold tabular-nums ${
          highlight ? 'text-red-600' : 'text-slate-800'
        }`}
      >
        {value.toLocaleString()}
      </div>
    </div>
  );
}
