import { ROLES } from 'enums/roles';
import React from 'react';
import useStore from 'store';

function withAuthorization<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  allowedRoles: ROLES[] = []
): React.FC<P> {
  const CheckRoles: React.FC<P> = ({ ...props }: P) => {
    const userInfo = useStore((x) => x.userInfo);
    const allowed = allowedRoles?.some((x) =>
      userInfo?.authorities.includes(x)
    );

    if (!userInfo) {
      return <span>Loading...</span>;
    }

    if (!allowed) {
      return <span>Unauthorized Access</span>;
    }

    return <WrappedComponent {...props} />;
  };

  return CheckRoles;
}

export default withAuthorization;
