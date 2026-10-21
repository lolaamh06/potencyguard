// The frame of every page except the Story: Back link, breadcrumb, title and one line saying what
// the page is for, the content, and the big "Next step" button of the guided flow.
import type { ReactNode } from "react";
import { SCENARIO_COPY } from "../copy/scenarios";
import { PAGE_INFO, backTarget, nextStep, routeHash, type Route } from "../app/route";

export function PageShell({ route, children, title, endActions }: { route: Route; children: ReactNode; title?: string; endActions?: ReactNode }) {
  const info = PAGE_INFO[route.page];
  const back = backTarget(route);
  const next = nextStep(route);
  const heading = title ?? (route.page === "shipment" && route.id ? SCENARIO_COPY[route.id].title : info.title);
  return (
    <main id="content" className="page" tabIndex={-1}>
      <div className="page-head">
        {route.page === "shipment" && (
          <nav aria-label="Breadcrumb" className="crumbs">
            <a href="#/shipments">Shipments</a> <span aria-hidden="true">›</span> <span aria-current="page">{heading}</span>
          </nav>
        )}
        {back && <a className="back" href={routeHash(back)}>← Back</a>}
        <h1>{heading}</h1>
        <p className="lead">{info.lead}</p>
      </div>
      {children}
      {(next || endActions) && route.page !== "home" && (
        <div className="next-step">
          {next && <a className="btn primary big" href={routeHash(next.route)} data-tour={route.page === "shipments" ? undefined : undefined}>{next.label} →</a>}
          {endActions}
        </div>
      )}
    </main>
  );
}
