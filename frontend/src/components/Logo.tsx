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
      <circle cx="12" cy="12" r="10" opacity={0.15} fill="currentColor" stroke="none" />
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </svg>
  );
}
