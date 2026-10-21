// A branded, calm fallback so the app never shows a blank screen.
import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

export class ErrorBoundary extends Component<Props, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.warn("PotencyGuard view failed.", error.message, info.componentStack ?? "");
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="page" role="alert">
        <div className="fallback-card">
          <h1>PotencyGuard</h1>
          <p>Something went wrong while drawing this view. Nothing has been lost: the data on this page are simulated.</p>
          <button className="btn" type="button" onClick={() => window.location.reload()}>
            Reload the page
          </button>
        </div>
      </main>
    );
  }
}
