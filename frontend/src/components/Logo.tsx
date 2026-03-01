interface LogoProps {
  className?: string;
}

export default function Logo({ className = "h-7 w-7" }: LogoProps) {
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
      aria-hidden="true"
    >
      <path
        d="M12 3C8.5 3 6 5.5 6 8.5c0 4.5 6 10.5 6 10.5s6-6 6-10.5C18 5.5 15.5 3 12 3z"
        fill="currentColor"
        opacity={0.15}
      />
      <path d="M12 3C8.5 3 6 5.5 6 8.5c0 4.5 6 10.5 6 10.5s6-6 6-10.5C18 5.5 15.5 3 12 3z" />
      <polyline points="4 12 8 12 9.5 9 12 15 14.5 9 16 12 20 12" />
    </svg>
  );
}
