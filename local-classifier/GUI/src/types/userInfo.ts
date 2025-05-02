export interface UserInfo {
  JWTCreated: string;
  JWTExpirationTimestamp: string;
  firstName: string;
  lastName: string;
  loggedInDate: string;
  loginExpireDate: string;
  authMethod: string;
  fullName: string;
  authorities: string[];
  displayName: string;
  userIdCode: string;
  email: string;
  csaEmail: string;
  csaTitle: string;
}
