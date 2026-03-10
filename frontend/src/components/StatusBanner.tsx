type StatusBannerProps = {
  type: "ok" | "error";
  message: string;
  onClose?: () => void;
};

export function StatusBanner({ type, message, onClose }: StatusBannerProps) {
  return (
    <div className={`status-banner status-${type}`}>
      <span className="status-banner-message">{message}</span>
      {onClose ? (
        <button
          type="button"
          className="status-banner-close"
          onClick={onClose}
          aria-label="Close notification"
        >
          ×
        </button>
      ) : null}
    </div>
  );
}
