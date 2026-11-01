import { NextRequest } from 'next/server';
import { createProvider, type ScanTargetOptions } from '@/lib/scanner/providers';
import { runScan, type ScanEvent } from '@/lib/scanner/engine';
import { logSmb, sanitizeTarget } from '@/lib/scanner/smb-debug-log';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface ScanRequestBody extends ScanTargetOptions {
  maxDepth?: number;
  enableEntropy?: boolean;
}
export async function POST(request: NextRequest) {
  let body: ScanRequestBody;
  try {
    body = (await request.json()) as ScanRequestBody;
  } catch {
    return Response.json({ error: '请求体必须是合法 JSON' }, { status: 400 });
  }

  if (body.mode !== 'local' && body.mode !== 'smb') {
    return Response.json({ error: 'mode 必须是 local 或 smb' }, { status: 400 });
  }
  if (body.mode === 'local' && !body.path) {
    return Response.json({ error: 'local 模式缺少 path' }, { status: 400 });
  }
  if (body.mode === 'smb' && (!body.host || !body.share)) {
    return Response.json({ error: 'smb 模式缺少 host 或 share' }, { status: 400 });
  }

  // 记录本次请求的实际参数（密码已脱敏），便于排查「为什么登不上」
  await logSmb('INFO', 'scan.request', {
    mode: body.mode,
    target: sanitizeTarget({
      host: body.host,
      share: body.share,
      username: body.username,
      password: body.password,
      domain: body.domain,
    }),
    maxDepth: body.maxDepth ?? null,
    enableEntropy: body.enableEntropy ?? null,
    clientIp: request.headers.get('x-forwarded-for') ?? 'unknown',
  });

  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const send = (event: ScanEvent) => {
        controller.enqueue(
          encoder.encode(`data: ${JSON.stringify(event)}\n\n`)
        );
      };
      try {
        const provider = createProvider(body);
        const scan = runScan(provider, {
          maxDepth: body.maxDepth,
          enableEntropy: body.enableEntropy,
        });
        for await (const event of scan) {
          if (event.type === 'error') {
            await logSmb('ERROR', 'scan.error', { message: event.data });
          } else if (event.type === 'done') {
            await logSmb('INFO', 'scan.done', {
              riskLevel: event.data.riskLevel,
              filesScanned: event.data.stats.filesScanned,
              findings: event.data.findings.length,
              durationMs: event.data.durationMs,
            });
          }
          send(event);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        await logSmb('ERROR', 'scan.exception', { message });
        send({ type: 'error', data: message });
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'Transfer-Encoding': 'chunked',
    },
  });
}
