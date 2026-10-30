import { SyncStatus } from 'enums/datasetEnums';
export interface Agency {
    id?: string;
    agencyId: string;
    agencyName: string;
    groupKey: string;
    isLatest: boolean;
    deploymentStatus: "undeployed" | "deployed" | "deploying" | "failed";
    isEnabled: boolean;
    agencyDataHash: string;
    enableAllowed: boolean;
    lastModelTrained: string;
    lastUpdatedTimestamp:  Date | null |undefined;
    lastTrainedTimestamp:  Date | null |undefined;
    syncStatus: SyncStatus;
    partOfNetwork: boolean;
    createdAt: string;
  }