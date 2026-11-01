import { NextRequest } from 'next/server';
import { checkDsmVersion } from '@/lib/scanner/dsm';

export const runtime = 'nodejs';

export async function POST(request: NextRequest) {
  let body: { version?: string };
  try {
    body = (await request.json()) as { version?: string };
  } catch {
    return Response.json({ error: '请求体必须是合法 JSON' }, { status: 400 });
  }
  if (!body.version || typeof body.version !== 'string') {
    return Response.json({ error: '缺少 version 字段' }, { status: 400 });
  }
  const result = checkDsmVersion(body.version);
  if (!result) {
    return Response.json(
      { error: '无法解析版本号，示例格式：DSM 7.2.1-69057 Update 6' },
      { status: 400 }
    );
  }
  return Response.json(result);
}
