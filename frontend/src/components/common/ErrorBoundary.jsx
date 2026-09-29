import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '24px', margin: '20px', background: '#fee2e2', border: '1px solid #f87171', borderRadius: '8px', color: '#991b1b' }}>
          <h2 style={{ margin: '0 0 10px 0', fontSize: '18px' }}>Something went wrong while rendering this view.</h2>
          <p style={{ margin: '0 0 12px 0', fontFamily: 'monospace', fontSize: '13px' }}>
            {this.state.error?.message || String(this.state.error)}
          </p>
          <button
            onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload(); }}
            style={{ padding: '8px 16px', background: '#dc2626', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 600 }}
          >
            Reload Console
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}