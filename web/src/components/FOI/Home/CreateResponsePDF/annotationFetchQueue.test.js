import { runWithConcurrencyLimit } from "./annotationFetchQueue";

const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

describe("runWithConcurrencyLimit", () => {
  it("does not run more than the configured number of tasks at once", async () => {
    const first = deferred();
    const second = deferred();
    const third = deferred();
    const started = [];

    const tasks = [
      () => {
        started.push("first");
        return first.promise;
      },
      () => {
        started.push("second");
        return second.promise;
      },
      () => {
        started.push("third");
        return third.promise;
      },
    ];

    const resultPromise = runWithConcurrencyLimit(tasks, 2);

    await Promise.resolve();
    expect(started).toEqual(["first", "second"]);

    first.resolve("a");
    await Promise.resolve();
    expect(started).toEqual(["first", "second", "third"]);

    second.resolve("b");
    third.resolve("c");

    await expect(resultPromise).resolves.toEqual(["a", "b", "c"]);
  });

  it("rejects when a task fails", async () => {
    const tasks = [
      () => Promise.resolve("a"),
      () => Promise.reject(new Error("annotation fetch failed")),
      () => Promise.resolve("c"),
    ];

    await expect(runWithConcurrencyLimit(tasks, 2)).rejects.toThrow("annotation fetch failed");
  });
});
