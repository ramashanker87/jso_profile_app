import logo from "../assets/jso.jpg";

export function Logo({ className = "" }: { className?: string }) {
  return (
    <img
      src={logo}
      alt="Jan Suraaj Overseas (JSO)"
      width={400}
      height={400}
      className={`jso-logo ${className}`}
    />
  );
}
