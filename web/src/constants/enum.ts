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
  GCP: "GCP Ministry Team",
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
  MSD: "MSD Ministry Team",
  OBC: "OBC Ministry Team",
  OCC: "OCC Ministry Team",
  OOP: "OOP Ministry Team",
  PSA: "PSA Ministry Team",
  PSSG: "PSSG Ministry Team",
  TACS: "TACS Ministry Team",
  TIC: "TIC Ministry Team",
  TRAN: "TRAN Ministry Team"
};

const pageFlagTypes:pageFlagType = {
  "No Flag": 0,
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
  [key: string]: string
}

const RequestStates:RequestStatesType = {
  "Open": "open",
  "Call For Records": "callforrecords",
  "Closed": "closed",
  "Redirect": "redirect",
  "Unopened": "unopened",
  "Intake in Progress": "intakeinprogress",
  "Records Review": "recordsreview",
  "Fee Estimate": "feeestimate",
  "Consult": "consult",
  "Ministry Sign Off": "ministrysignoff",
  "On Hold": "onhold",
  "Deduplication": "deduplication",
  "Harms Assessment": "harmsassessment",
  "Response": "response",
  "Archived": "archived",
  "Peer Review": "peerreview",
  "Call For Records Overdue": "callforrecordsoverdue"
};


export {
  KCProcessingTeams,
  MINISTRYGROUPS,
  pageFlagTypes,
  RequestStates
};