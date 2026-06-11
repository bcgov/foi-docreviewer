import { fetchDocumentAnnotations } from "./docReviewerService";
import { httpGETBigRequest } from "../httpRequestHandler";

jest.mock("../httpRequestHandler", () => ({
  httpGETRequest: jest.fn(),
  httpGETBigRequest: jest.fn(),
  httpPOSTRequest: jest.fn(),
  httpGETRequestSOLR: jest.fn(),
}));

jest.mock("../../services/UserService", () => ({
  __esModule: true,
  default: {
    getToken: jest.fn(() => "token-123"),
  },
  getToken: jest.fn(() => "token-123"),
}));

jest.mock("../../services/StoreService", () => ({
  store: {
    dispatch: jest.fn(),
  },
}));

jest.mock("../endpoints", () => ({
  __esModule: true,
  default: {
    DOCREVIEWER_ANNOTATION: "http://docreviewer/api/annotation",
  },
}));

const mockedHttpGETBigRequest = httpGETBigRequest as jest.MockedFunction<typeof httpGETBigRequest>;

describe("fetchDocumentAnnotations", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    const userServiceModule = require("../../services/UserService");
    userServiceModule.default.getToken.mockReturnValue("token-123");
    userServiceModule.getToken.mockReturnValue("token-123");
  });

  it("passes the configured timeout to httpGETBigRequest", async () => {
    mockedHttpGETBigRequest.mockResolvedValueOnce({ data: { 42: ["<redact />"] } } as any);
    const callback = jest.fn();
    const errorCallback = jest.fn();

    fetchDocumentAnnotations(51081, "redline", 42, callback, errorCallback, 900000);
    await Promise.resolve();
    await Promise.resolve();

    expect(mockedHttpGETBigRequest).toHaveBeenCalledWith(
      "http://docreviewer/api/annotation/51081/redline/document/42",
      {},
      "token-123",
      900000
    );
    expect(callback).toHaveBeenCalledWith({ 42: ["<redact />"] });
    expect(errorCallback).not.toHaveBeenCalled();
  });

  it("calls errorCallback with structured details when the annotation request fails", async () => {
    const requestError = {
      response: {
        status: 504,
        data: { message: "Gateway Timeout" },
      },
    };
    mockedHttpGETBigRequest.mockRejectedValueOnce(requestError);
    const callback = jest.fn();
    const errorCallback = jest.fn();

    fetchDocumentAnnotations(51081, "redline", 42, callback, errorCallback, 900000);
    await Promise.resolve();
    await Promise.resolve();

    expect(callback).not.toHaveBeenCalled();
    expect(errorCallback).toHaveBeenCalledWith({
      message: "Error in fetching annotations for a document",
      url: "http://docreviewer/api/annotation/51081/redline/document/42",
      status: 504,
      response: { message: "Gateway Timeout" },
      error: requestError,
    });
  });
});
