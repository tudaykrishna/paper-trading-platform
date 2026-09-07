import React from "react";

interface State {
  error: Error | null;
}

/** Shows the error instead of a blank white page when a render throws. */
export default class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  State
> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("UI crashed:", error, info);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div style={{ padding: 24, fontFamily: "system-ui, sans-serif" }}>
        <h1 style={{ color: "#dc2626" }}>Something broke while rendering</h1>
        <p>Open the browser console for the full stack trace. Error:</p>
        <pre
          style={{
            background: "#f1f5f9",
            padding: 12,
            borderRadius: 8,
            overflowX: "auto",
            whiteSpace: "pre-wrap",
          }}
        >
          {this.state.error.message}
          {"\n\n"}
          {this.state.error.stack}
        </pre>
        <button
          onClick={() => {
            try {
              localStorage.clear();
            } catch {
              /* ignore */
            }
            location.reload();
          }}
          style={{
            padding: "8px 14px",
            borderRadius: 6,
            border: "1px solid #cbd5e1",
            cursor: "pointer",
          }}
        >
          Clear local storage &amp; reload
        </button>
      </div>
    );
  }
}
