import { create } from 'zustand';
import { UserInfo } from 'types/userInfo';

interface StoreState {
  userInfo: UserInfo | null;
  userId: string;
  setUserInfo: (info: UserInfo) => void;
}

const useStore = create<StoreState>((set) => ({
  userInfo: null,
  userId: '',
  setUserInfo: (data) => set({ userInfo: data, userId: data?.userIdCode || '' }),
}));

export default useStore;
