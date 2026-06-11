export const runWithConcurrencyLimit = async (tasks, limit) => {
  if (!Array.isArray(tasks)) {
    throw new TypeError("tasks must be an array");
  }

  if (tasks.length === 0) {
    return [];
  }

  const concurrency = Math.max(1, Math.min(limit || 1, tasks.length));
  const results = new Array(tasks.length);
  let nextIndex = 0;
  let firstError;

  const worker = async () => {
    while (!firstError) {
      const currentIndex = nextIndex;
      if (currentIndex >= tasks.length) return;
      nextIndex += 1;

      try {
        results[currentIndex] = await tasks[currentIndex]();
      } catch (err) {
        firstError = err;
        throw err;
      }
    }
  };

  await Promise.all(Array.from({ length: concurrency }, () => worker()));
  return results;
};
