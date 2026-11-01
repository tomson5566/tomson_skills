'use client';

import { useCallback, useState } from 'react';
import { ShieldCheck, ShieldAlert, Search, Download } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import type { DsmCheckResult } from '@/lib/scanner/dsm';

export function DsmChecker() {
  const [version, setVersion] = useState('DSM 7.2.1-69057 Update 6');
  const [result, setResult] = useState<DsmCheckResult | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const check = useCallback(async () => {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await fetch('/api/dsm-check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ version }),
      });
      const data = (await res.json()) as DsmCheckResult & { error?: string };
      if (!res.ok) {
        setError(data.error ?? `HTTP ${res.status}`);
      } else {
        setResult(data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [version]);

  const downloadScript = useCallback(async () => {
    const res = await fetch('/api/nas-script');
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'nas_ransomware_check.sh';
    link.click();
    window.URL.revokeObjectURL(url);
  }, []);

  return (
    <div className="space-y-6">
      {/* DSM 版本自检 */}
      <Card className="border-slate-200">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-[#1E3A5F] text-lg">
            <Search className="size-5" />
            DSM 版本漏洞自检
          </CardTitle>
          <CardDescription>
            粘贴「控制面板 → 系统更新」中显示的版本号，比对是否包含 Synology-SA-26:13 修复
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="dsm-version">DSM 版本</Label>
            <div className="flex gap-2">
              <Input
                id="dsm-version"
                value={version}
                onChange={(e) => setVersion(e.target.value)}
                placeholder="DSM 7.2.1-69057 Update 6"
                className="font-mono"
                onKeyDown={(e) => e.key === 'Enter' && check()}
              />
              <Button
                onClick={check}
                disabled={loading || !version.trim()}
                variant="outline"
                className="shrink-0"
              >
                检测
              </Button>
            </div>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          {result && (
            <div
              className={`rounded-lg border p-4 space-y-3 ${
                result.affected
                  ? 'border-red-300 bg-red-50'
                  : result.knownTrain
                    ? 'border-emerald-300 bg-emerald-50'
                    : 'border-slate-300 bg-slate-50'
              }`}
            >
              <div className="flex items-center gap-2 flex-wrap">
                {result.affected ? (
                  <>
                    <ShieldAlert className="size-5 text-red-600" />
                    <span className="font-semibold text-red-700">
                      存在漏洞：当前版本可被 C3RB3R 勒索软件利用
                    </span>
                  </>
                ) : result.knownTrain ? (
                  <>
                    <ShieldCheck className="size-5 text-emerald-600" />
                    <span className="font-semibold text-emerald-700">
                      已包含修复，不受本轮攻击影响
                    </span>
                  </>
                ) : (
                  <span className="font-semibold text-slate-700">未知版本线</span>
                )}
              </div>
              <div className="flex gap-2 flex-wrap">
                {result.cves.map((c) => (
                  <Badge key={c.id} variant="outline" className="font-mono">
                    {c.id} · CVSS {c.cvss}
                  </Badge>
                ))}
              </div>
              <ul className="space-y-1.5 text-sm text-slate-700 list-disc pl-5">
                {result.advice.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      {/* NAS 端巡检脚本 */}
      <Card className="border-slate-200">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-[#1E3A5F] text-lg">
            <Download className="size-5" />
            NAS 端定时巡检脚本
          </CardTitle>
          <CardDescription>
            下载后粘贴到「控制面板 → 任务计划 → 用户定义的脚本」，建议每 30 分钟运行一次
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <ul className="text-sm text-slate-600 space-y-1.5 list-disc pl-5">
            <li>扫描 .L0CK3D 加密文件与 read-me3.txt 等勒索信特征</li>
            <li>检测 1 小时内批量文件修改（加密行为特征）</li>
            <li>排查可疑计划任务后门、异常可登录账号、暴力破解痕迹</li>
            <li>蜜罐文件完整性校验，支持 Webhook 告警推送</li>
          </ul>
          <Button onClick={downloadScript} variant="outline" className="font-mono">
            <Download className="size-4" />
            nas_ransomware_check.sh
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
