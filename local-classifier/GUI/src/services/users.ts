import apiDev from './api-dev';
import { User, UserDTO } from 'types/user';

export async function createUser(userData: UserDTO) {
  const authorities = userData.authorities.map((e) => (e as any).value).filter(item => item);
  const fullName = userData.fullName?.trim();
  const nameLength = fullName?.split(" ")?.length;
  const { data } = await apiDev.post<User>('classifier/accounts/add', {
    "firstName": fullName?.split(' ').slice(0, 1).join(' ') ?? '',
    "lastName": fullName?.split(' ').slice(1, nameLength).join(' ') ?? '',
    "userIdCode": userData.useridcode,
    "displayName": userData.fullName,
    "csaTitle": userData.csaTitle,
    "csa_email": userData.csaEmail,
    "roles": authorities.length === 0 ? Object.values(userData.authorities) : authorities
  });
  return data;
}

export async function checkIfUserExists(userData: UserDTO) {
  const { data } = await apiDev.post('classifier/accounts/exists', {
    "userIdCode": userData.useridcode
  });
  return data;
}

export async function editUser(id: string | number, userData: UserDTO) {
  const authorities = userData.authorities.map((e: any) => e.value).filter(item => item);
  const fullName = userData.fullName?.trim();
  const nameLength = fullName?.split(" ")?.length;
  const { data } = await apiDev.post<User>('classifier/accounts/edit', {
    "firstName": fullName?.split(' ').slice(0, 1).join(' ') ?? '',
    "lastName": fullName?.split(' ').slice(1, nameLength).join(' ') ?? '',
    "userIdCode": id,
    "displayName": userData.fullName,
    "csaTitle": userData.csaTitle,
    "csa_email": userData.csaEmail,
    "roles": authorities.length === 0 ? Object.values(userData.authorities) : authorities
  });
  return data;
}

export async function deleteUser(id: string | number) {
  const { data } = await apiDev.post<User>('classifier/accounts/delete', {
    "userIdCode": id,
  });
  return data;
}
