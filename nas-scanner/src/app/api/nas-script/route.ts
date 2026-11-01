import { generateNasScript } from '@/lib/scanner/nas-script';

export const runtime = 'nodejs';

export async function GET() {
  const script = generateNasScript();
  return new Response(script, {
    headers: {
      'Content-Type': 'text/x-sh; charset=utf-8',
      'Content-Disposition': 'attachment; filename="nas_ransomware_check.sh"',
    },
  });
}
