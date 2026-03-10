type StatusBannerProps = {
  type: "ok" | "error";
  message: string;
};

export function StatusBanner({ type, message }: StatusBannerProps) {
  return <div className={`status-banner status-${type}`}>{message}</div>;
}
