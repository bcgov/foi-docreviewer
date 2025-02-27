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
  "Phase": 9
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

type RedactionType = {
  [key: string]: string
}
const RedactionTypes: RedactionType = {
  "fullpage": "fullpage",
  "partial": "partial",
  "nr": "nr",
  "blank": "blank"
};

const MCFPopularSections = 21

type MSDSortingType = {
  [key: string]: Number
}

const MSDDivisionsSorting: MSDSortingType = {
  "FASB": 1,
  "GA KEY PLAYER AHR": 2,
  "GA KEY PLAYER": 3,
  "GA KEY PLAYER PHYSICAL": 4,
  "TPA": 5,
  "ELMSD": 6,
  "PLMS": 7,
  "FM1 KEY PLAYER AHR": 8,
  "FM1 KEY PLAYER": 9,
  "FM1 KEY PLAYER PHYSICAL": 10,
  "GA SPOUSE AHR": 11,
  "GA SPOUSE": 12,
  "GA SPOUSE PHYSICAL": 13,
  "GA 2 SPOUSE AHR": 14,
  "GA 2 SPOUSE": 15,
  "GA2 SPOUSE PHYSICAL": 16,
  "GA 3 SPOUSE AHR": 17,
  "GA 3 SPOUSE": 18,
  "GA3 SPOUSE PHYSICAL": 19,
  "FM2 RESPONDENT AHR": 20,
  "FM2 RESPONDENT": 21,
  "FM2 RESPONDENT PHYSICAL": 22,
  "FM3 AHR": 23,
  "FM3": 24,
  "FM3 PHYSICAL": 25,
  "FM4 AHR": 26,
  "FM4": 27,
  "FM4 PHYSICAL": 28,
  "FM5 AHR": 29,
  "FM5": 30,
  "FM5 PHYSICAL": 31,
  "GA DEPENDENT AHR": 32,
  "GA DEPENDENT": 33,
  "GA DEPENDENT PHYSICAL": 34,
  "GA 2 DEPENDENT AHR": 35,
  "GA 2 DEPENDENT": 36,
  "GA2 DEPENDENT PHYSICAL": 37,
  "SHRC": 38,
  "ISD": 39
}

export {
  KCProcessingTeams,
  MINISTRYGROUPS,
  pageFlagTypes,
  RequestStates,
  RedactionTypes,
  MCFPopularSections,
  MSDDivisionsSorting
};