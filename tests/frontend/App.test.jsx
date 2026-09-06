import React from 'react';
import { render } from '@testing-library/react';
import App from '../../frontend/src/App.jsx';

it('renders the BharatRisk dashboard title', () => {
  const { getAllByText } = render(<App />);
  expect(getAllByText('BHARATRISK AI').length).toBeGreaterThan(0);
});
