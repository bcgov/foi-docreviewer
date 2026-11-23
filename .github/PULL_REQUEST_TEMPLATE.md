<!-- Describe the changes in this pull request. -->

---

> **This section is mandatory only for pull requests targeting the `main` branch.**

## Release Label

<!--
Enter a release label using one of these formats:

MAJOR
MAJOR.MINOR
MAJOR.MINOR.PATCH

Examples: 25, 25.99, 25.99.99
-->

Release Label: <YOUR-RELEASE-LABEL>

### Why is this required?

The Release Label identifies which services are included in a release. Our production workflow uses it to select and promote the correct service images and trigger database backups when required.

**IMPORTANT: You will not be able to merge your pull request into `main` without a valid Release Label.**