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
    syncStatus: "Unavailable_in_CKB" | "Available_in_CKB" | "Syncing" | "Failed";
    createdAt: string;
  }