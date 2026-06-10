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

  const worker = async () => {
    while (nextIndex < tasks.length) {
      const currentIndex = nextIndex;
      nextIndex += 1;
      results[currentIndex] = await tasks[currentIndex]();
    }
  };

  await Promise.all(Array.from({ length: concurrency }, worker));
  return results;
};
