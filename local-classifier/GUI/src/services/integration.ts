import { OperationConfig } from 'types/integration';
import apiDev from './api-dev';

export async function getIntegrationStatus() {
    const { data } = await apiDev.get('classifier/integration/platform-status');
    return data?.response;
  }

  export async function togglePlatform(integrationData: OperationConfig) {
    const { data } = await apiDev.post('classifier/integration/toggle-platform', {
      "operation": integrationData.operation,
      "platform": integrationData.platform
    });
    return data;
  }