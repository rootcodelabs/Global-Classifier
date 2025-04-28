import { ReactNode } from 'react';

export interface MenuItem {
  id?: string;
  label: string;
  path: string | null;
  target?: '_blank' | '_self';
  children?: MenuItem[];
  icon?: ReactNode;
}

export interface MainNavigation {
  data: MenuItem[];
}
