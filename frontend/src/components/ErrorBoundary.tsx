import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertOctagon, RotateCw } from "lucide-react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught an unhandled error:", error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-[50vh] flex items-center justify-center p-6">
          <div className="card max-w-lg w-full text-center space-y-4 border-rose-200 dark:border-rose-900/50">
            <div className="mx-auto w-12 h-12 rounded-full bg-rose-100 dark:bg-rose-950/60 flex items-center justify-center text-rose-600 dark:text-rose-400">
              <AlertOctagon size={24} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-900 dark:text-white">Something went wrong</h2>
              <p className="muted text-sm mt-1">
                An unexpected interface error occurred. You can reload the page or navigate back safely.
              </p>
              {this.state.error && (
                <div className="mt-3 p-3 rounded-xl bg-slate-100 dark:bg-navy-950 text-left font-mono text-xs text-rose-600 dark:text-rose-400 overflow-x-auto">
                  {this.state.error.message}
                </div>
              )}
            </div>
            <div className="flex justify-center gap-3 pt-2">
              <button onClick={this.handleReset} className="btn">
                <RotateCw size={15} /> Reload Application
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
