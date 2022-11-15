import React , { useState } from 'react';
import { render, screen } from '@testing-library/react';
import DocumentSelector from './DocumentSelector';

test('renders document selector', () => {
  const files: any[] = [
    {"documentid": 1, "filename": "sample1.pdf", "filepath": "/files/", "foiministryrequestid": 1, "lastmodified": "2022-11-14T00:04:36.549002-08:00", "pagecount": 9, "version": 1, "divisions": [{"divisionid": 1, "isactive": true, "name": "Minister's Office", "programareaid": 6}]},
    {"documentid": 2, "filename": "sample2.pdf", "filepath": "/files/", "foiministryrequestid": 1, "lastmodified": "2022-11-14T00:04:36.549008-08:00", "pagecount": 2, "version": 1, "divisions": [{"divisionid": 1, "isactive": true, "name": "Minister's Office", "programareaid": 6}]},
  ];
  const currentPageInfo = {'file': files[0], 'page': 1};
  const setCurrentPageInfo = () => {};

  render(<DocumentSelector documents={files} currentPageInfo={currentPageInfo} setCurrentPageInfo={setCurrentPageInfo} />);
  const linkElement = screen.getByText(/Organize by/i);
  expect(linkElement).toBeInTheDocument();
});
