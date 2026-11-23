export const setGenericPassword = async (
  _username: string,
  password: string,
  options?: { service?: string }
): Promise<boolean> => {
  const key = options?.service ? `keychain_${options.service}` : 'keychain_default';
  localStorage.setItem(key, JSON.stringify({ username: _username, password }));
  return true;
};

export const getGenericPassword = async (options?: { service?: string }): Promise<{ username: string; password: string } | false> => {
  const key = options?.service ? `keychain_${options.service}` : 'keychain_default';
  const item = localStorage.getItem(key);
  if (!item) return false;
  try {
    return JSON.parse(item);
  } catch {
    return false;
  }
};

export const resetGenericPassword = async (options?: { service?: string }): Promise<boolean> => {
  const key = options?.service ? `keychain_${options.service}` : 'keychain_default';
  localStorage.removeItem(key);
  return true;
};

const keychainMock = {
  setGenericPassword,
  getGenericPassword,
  resetGenericPassword,
};

export default keychainMock;
