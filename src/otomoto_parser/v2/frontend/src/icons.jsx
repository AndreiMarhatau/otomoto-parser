import React from "react";

function icon(path) {
  return function Icon() {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        {path}
      </svg>
    );
  };
}

export const IconRefresh = icon(<><path d="M20 12a8 8 0 1 1-2.34-5.66" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /><path d="M20 4v6h-6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></>);
export const IconAlert = icon(<><path d="M12 3l9 16H3l9-16z" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" /><path d="M12 9v4.5" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" /><circle cx="12" cy="16.8" r="1" fill="currentColor" /></>);
export const IconClose = icon(<path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />);
export const IconTrash = icon(<path d="M4 7h16M9 7V4h6v3M8 7l1 12h6l1-12" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />);
export const IconExternal = icon(<><path d="M14 5h5v5M19 5l-8 8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /><path d="M19 14v4a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></>);
export const IconReport = icon(<><path d="M8 4h8l4 4v10a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /><path d="M16 4v4h4M9 12h6M9 16h6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></>);
export const IconCheckBadge = icon(<><path d="M12 2l2.1 2.3 3.1-.3 1.2 2.8 2.8 1.2-.3 3.1L23 13l-2.1 2.3.3 3.1-2.8 1.2-1.2 2.8-3.1-.3L12 24l-2.3-2.1-3.1.3-1.2-2.8-2.8-1.2.3-3.1L1 13l2.1-2.3-.3-3.1 2.8-1.2 1.2-2.8 3.1.3z" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" /><path d="M8.5 12.5l2.3 2.3 4.7-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></>);
export const IconXBadge = icon(<><path d="M12 2l2.1 2.3 3.1-.3 1.2 2.8 2.8 1.2-.3 3.1L23 13l-2.1 2.3.3 3.1-2.8 1.2-1.2 2.8-3.1-.3L12 24l-2.3-2.1-3.1.3-1.2-2.8-2.8-1.2.3-3.1L1 13l2.1-2.3-.3-3.1 2.8-1.2 1.2-2.8 3.1.3z" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" /><path d="M9.2 9.2l5.6 5.6M14.8 9.2l-5.6 5.6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></>);
export const IconChevronLeft = icon(<path d="M14.5 6.5L9 12l5.5 5.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />);
export const IconChevronRight = icon(<path d="M9.5 6.5L15 12l-5.5 5.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />);
export const IconPlus = icon(<path d="M12 5v14M5 12h14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />);
export const IconEdit = icon(<><path d="M4 20l4.5-1 9-9-3.5-3.5-9 9L4 20z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /><path d="M12.5 6.5L16 10" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></>);
export const IconTag = icon(<><path d="M11 4H5v6l8 8 6-6-8-8z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /><circle cx="8" cy="8" r="1.2" fill="currentColor" /></>);
export const IconStar = icon(<path d="M12 3.8l2.6 5.3 5.8.8-4.2 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.2-4.1 5.8-.8L12 3.8z" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />);
