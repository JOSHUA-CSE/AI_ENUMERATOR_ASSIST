import type { NativeStackNavigationProp, NativeStackScreenProps } from '@react-navigation/native-stack';

// Auth Navigator Param List
export type AuthStackParamList = {
  Login: undefined;
};

export type AuthScreenProps<T extends keyof AuthStackParamList> = NativeStackScreenProps<
  AuthStackParamList,
  T
>;

// Deputy Navigator Param List
export type DeputyStackParamList = {
  DeputyDashboard: undefined;
  AreaList: undefined;
  AreaMap: { areaId: string; areaName: string; areaCode: string };
  LayoutList: { areaId?: string; areaName?: string } | undefined;
  HlbGeneration: { areaId: string; areaName?: string; layoutId?: string; layoutName?: string };
  HlbReview: { layoutId: string; areaName?: string; areaCode?: string; areaId?: string; candidateLayoutId?: string };
  LayoutsPlaceholder: undefined;
  SupervisorsPlaceholder: undefined;
  ProgressPlaceholder: undefined;
  DeputySupervisors: undefined;
  DeputyProgress: undefined;
  DeputyChangeRequests: undefined;
  DeputyLayoutDetail: {
    layoutId: string;
    layoutName?: string;
    areaName?: string;
    areaId?: string;
  };
};


export type DeputyScreenProps<T extends keyof DeputyStackParamList> = NativeStackScreenProps<
  DeputyStackParamList,
  T
>;

export type DeputyNavigationProp = NativeStackNavigationProp<DeputyStackParamList>;

// Supervisor Navigator Param List
export type SupervisorStackParamList = {
  SupervisorDashboard: undefined;
  SupervisorLayoutDetail: {
    layoutId: string;
    layoutName?: string;
    areaName?: string;
    areaId?: string;
  };
  SupervisorVerification: { layoutId?: string; hlbId?: string } | undefined;
  SupervisorChangeRequests: { layoutId?: string } | undefined;
  AssignedLayoutsPlaceholder: undefined;
  EnumeratorsPlaceholder: undefined;
  ProgressPlaceholder: undefined;
};

export type SupervisorScreenProps<T extends keyof SupervisorStackParamList> = NativeStackScreenProps<
  SupervisorStackParamList,
  T
>;

export type SupervisorNavigationProp = NativeStackNavigationProp<SupervisorStackParamList>;

// Enumerator Navigator Param List
export type EnumeratorStackParamList = {
  EnumeratorDashboard: undefined;
  EnumeratorHlbDetail: { hlbId: string; blockCode?: string };
  BuildingDetail: { buildingId: string; hlbId: string; blockCode?: string };
  HouseholdForm: {
    buildingId: string;
    hlbId: string;
    householdId?: string;
    censusHouseId?: string;
    buildingReference?: string;
  };
  MyHLBPlaceholder: undefined;
  TodaysProgressPlaceholder: undefined;
  PendingHousesPlaceholder: undefined;
  SyncStatusPlaceholder: undefined;
};


export type EnumeratorScreenProps<T extends keyof EnumeratorStackParamList> = NativeStackScreenProps<
  EnumeratorStackParamList,
  T
>;

export type EnumeratorNavigationProp = NativeStackNavigationProp<EnumeratorStackParamList>;

// Root Param List
export type RootStackParamList = {
  Auth: undefined;
  Deputy: undefined;
  Supervisor: undefined;
  Enumerator: undefined;
};
