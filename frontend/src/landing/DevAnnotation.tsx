import { lazy, Suspense } from 'react';

// Dev-only visual feedback toolbar (Agentation, agentation.com). In production
// builds import.meta.env.DEV is false, the lazy branch tree-shakes away and
// the toolbar never loads.
const Agentation = import.meta.env.DEV
  ? lazy(() => import('agentation').then((m) => ({ default: m.Agentation })))
  : null;

export const DevAnnotation = () =>
  Agentation ? (
    <Suspense fallback={null}>
      <Agentation />
    </Suspense>
  ) : null;
