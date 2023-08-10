const KCProcessingTeams = [
  "Scanning Team",
  "Business Team",
  "Central Team",
  "Justice Health Team",
  "MCFD Personals Team",
  "Resource Team",
  "Social Education"]

type ministryType = {
  [key: string]: string
}

type pageFlagType = {
  [key: string]: number
}

const MINISTRYGROUPS: ministryType = {
  AEST: "AEST Ministry Team",
  AGR: "AGR Ministry Team",
  BRD: "BRD Ministry Team",
  CAS: "CAS Ministry Team",
  MCF: "MCF Ministry Team",
  CLB: "CLB Ministry Team",
  CITZ: "CITZ Ministry Team",
  DAS: "DAS Ministry Team",
  EAO: "EAO Ministry Team",
  EDU: "EDU Ministry Team",
  EMBC: "EMBC Ministry Team",
  EMLI: "EMLI Ministry Team",
  FIN: "FIN Ministry Team",
  FOR: "FOR Ministry Team",
  GCPE: "GCPE Ministry Team",
  HLTH: "HLTH Ministry Team",
  IIO: "IIO Ministry Team",
  IRR: "IRR Ministry Team",
  JERI: "JERI Ministry Team",
  LBR: "LBR Ministry Team",
  LDB: "LDB Ministry Team",
  LWR: "LWR Ministry Team",
  AG: "AG Ministry Team",
  MGC: "MGC Ministry Team",
  MMHA: "MMHA Ministry Team",
  MUNI: "MUNI Ministry Team",
  ENV: "ENV Ministry Team",
  SDPR: "SDPR Ministry Team",
  OBC: "OBC Ministry Team",
  OCC: "OCC Ministry Team",
  PREM: "PREM Ministry Team",
  PSA: "PSA Ministry Team",
  PSSG: "PSSG Ministry Team",
  TACS: "TACS Ministry Team",
  TIC: "TIC Ministry Team",
  TRAN: "TRAN Ministry Team"
};

const pageFlagTypes:pageFlagType = {
  "Partial Disclosure": 1,
  "Full Disclosure": 2,
  "Withheld in Full": 3,
  "Consult": 4,
  "Duplicate": 5,
  "Not Responsive": 6,
  "In Progress": 7,
  "Page Left Off": 8,
};

type RequestStatesType = {
  [key: string]: number
}

const RequestStates:RequestStatesType = {
  "Open": 1,
  "Call For Records": 2,
  "Closed": 3,
  "Redirect": 4,
  "Unopened": 5,
  "Intake in Progress": 6,
  "Records Review": 7,
  "Fee Estimate": 8,
  "Consult": 9,
  "Ministry Sign Off": 10,
  "On Hold": 11,
  "Deduplication": 12,
  "Harms Assessment": 13,
  "Response": 14,
  "Archived": 15,
  "Peer Review": 16,
  "Call For Records Overdue": 17
};

export {
  KCProcessingTeams,
  MINISTRYGROUPS,
  pageFlagTypes,
  RequestStates
};