interface LogoProps {
  className?: string;
}

export default function Logo({ className = "h-6 w-6" }: LogoProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <circle cx={12} cy={12} r={10} />
      <polyline points="6 12 9 12 11 8 13 16 15 12 18 12" />
    </svg>
  );
}
