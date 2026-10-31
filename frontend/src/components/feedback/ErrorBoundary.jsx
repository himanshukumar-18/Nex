import React from 'react';
import { AlertOctagon, RefreshCw } from 'lucide-react';
import Button from '@/components/ui/Button';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    // In production, send to telemetry/logging service
    console.error('NEX UI ErrorBoundary caught error:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-screen w-full flex items-center justify-center p-6 bg-bg-primary text-text-primary">
          <div className="w-full max-w-xl bg-surface-elevated border-2 border-status-danger p-6 rounded shadow-2xl flex flex-col gap-5">
            <div className="flex items-center gap-3 text-status-danger border-b border-border pb-4">
              <AlertOctagon className="w-6 h-6 shrink-0" />
              <div>
                <h2 className="text-base font-display font-bold uppercase tracking-wider">
                  NEX Client Runtime Exception
                </h2>
                <p className="text-xs font-mono text-text-secondary mt-0.5">
                  An unhandled error occurred in the React rendering tree.
                </p>
              </div>
            </div>

            <div className="bg-bg-secondary p-3 rounded border border-border">
              <p className="text-xs font-mono text-status-danger font-semibold">
                {this.state.error?.name || 'Error'}: {this.state.error?.message || 'Unknown error'}
              </p>
              {this.state.errorInfo?.componentStack && (
                <pre className="mt-2 text-[11px] font-mono text-text-secondary/80 overflow-x-auto max-h-40 leading-relaxed">
                  {this.state.errorInfo.componentStack}
                </pre>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <Button
                variant="outline"
                size="sm"
                leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
                onClick={this.handleReset}
              >
                Try Again
              </Button>
              <Button variant="danger" size="sm" onClick={this.handleReload}>
                Reload Application
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;

