interface LogoProps {
  className?: string;
}

/**
 * Synapse AI Gateway brand mark — "V7 Branching".
 *
 * One central indigo node with three short branches reaching three slate
 * satellite nodes. Reads as a neural cell / network topology — a central
 * authority mediating between connected endpoints.
 *
 * Colour control: the branches and satellite nodes use `currentColor`, so
 * the parent's `text-*` class drives them (white on the dark sidebar,
 * slate-900 on a light page). The central node is always indigo.
 */
export default function Logo({ className = '' }: LogoProps) {
  return (
    <svg
      viewBox="0 0 64 64"
      className={className}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Synapse AI Gateway"
    >
      {/* Branches */}
      <line x1="32" y1="32" x2="14" y2="14"
            stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
      <line x1="32" y1="32" x2="50" y2="14"
            stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
      <line x1="32" y1="32" x2="32" y2="54"
            stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
      {/* Satellite nodes */}
      <circle cx="14" cy="14" r="3.5" fill="currentColor" />
      <circle cx="50" cy="14" r="3.5" fill="currentColor" />
      <circle cx="32" cy="54" r="3.5" fill="currentColor" />
      {/* Central node — always indigo, never inherits */}
      <circle cx="32" cy="32" r="5.5" fill="#4F46E5" />
    </svg>
  );
}
