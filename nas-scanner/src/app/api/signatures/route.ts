import { RANSOMWARE_FAMILIES } from '@/lib/scanner/signatures';
import {
  C3RB3R_PRIORITY_EXTENSIONS,
  C3RB3R_EXCLUDED_DIRS,
} from '@/lib/scanner/c3rb3r-behavior';
import {
  HIGH_ENTROPY_THRESHOLD,
  PARTIAL_ENTROPY_DELTA,
  ENTROPY_SAMPLE_BYTES,
} from '@/lib/scanner/entropy';

export const runtime = 'nodejs';

export async function GET() {
  return Response.json({
    updatedAt: '2026-11-01',
    families: RANSOMWARE_FAMILIES.map((f) => ({
      id: f.id,
      name: f.name,
      description: f.description,
      extensions: f.extensions,
      ransomNotes: f.ransomNotes,
      ransomNoteSignatures: f.ransomNoteSignatures ?? [],
      targets: f.targets,
      severity: f.severity,
      reference: f.reference,
    })),
    /** C3RB3R 专项检测的辅助特征 */
    c3rb3r: {
      priorityExtensions: Array.from(C3RB3R_PRIORITY_EXTENSIONS).sort(),
      excludedDirs: C3RB3R_EXCLUDED_DIRS,
    },
    /** 熵值检测参数 */
    entropy: {
      threshold: HIGH_ENTROPY_THRESHOLD,
      partialDelta: PARTIAL_ENTROPY_DELTA,
      sampleBytes: ENTROPY_SAMPLE_BYTES,
    },
  });
}
