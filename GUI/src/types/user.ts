import { ROLES } from "enums/roles";

export interface User {
  login?: string;
  fullName?: string;
  firstName: string;
  lastName: string;
  useridcode: string;
  displayName: string;
  csaTitle: string;
  csaEmail: string;
  authorities: ROLES[];
  customerSupportStatus: 'online' | 'idle' | 'offline';
}

export interface UserDTO extends Pick<User, 'login' | 'firstName' | 'lastName' | 'fullName' | 'useridcode' | 'authorities' | 'displayName' | 'csaTitle' | 'csaEmail'> {
}
