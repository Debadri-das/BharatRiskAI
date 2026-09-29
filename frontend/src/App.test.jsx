import React from 'react';
import { render } from '@testing-library/react';
import App from './App.jsx';

if (typeof global.ResizeObserver === 'undefined') {
  global.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

it('renders the BharatRisk dashboard title', () => {
  const { getAllByText } = render(<App />);
  expect(getAllByText('BHARATRISK AI').length).toBeGreaterThan(0);
});
