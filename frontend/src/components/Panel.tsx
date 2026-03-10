import type { PropsWithChildren, ReactNode } from "react";
import clsx from "clsx";

type PanelProps = PropsWithChildren<{
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  className?: string;
}>;

export function Panel({ title, subtitle, actions, className, children }: PanelProps) {
  return (
    <section className={clsx("panel", className)}>
      <div className="panel-header">
        <div>
          <h2>{title}</h2>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
        {actions ? <div className="panel-actions">{actions}</div> : null}
      </div>
      <div>{children}</div>
    </section>
  );
}
