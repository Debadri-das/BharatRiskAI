import React from 'react';
export default class ErrorBoundary extends React.Component {
  state = { error: null };
  static getDerivedStateFromError(error) { return { error }; }
  render() { return this.state.error ? <div className="panel" style={{ padding: 18 }}>Something failed: {this.state.error.message}</div> : this.props.children; }
}
